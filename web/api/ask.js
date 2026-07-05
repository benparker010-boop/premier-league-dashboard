// Serverless route: Ask Parker.
// Calls the Anthropic API with the key kept SERVER-SIDE (process.env.ANTHROPIC_API_KEY).
// The prompt is grounded in our real prediction data + the current match context so
// the model only cites numbers we inject — it is told never to invent stats.
//
// Runs on Vercel (Node serverless) and, in local dev, via the Vite middleware in
// vite.config.js. Uses raw Node req/res so the same handler works in both.

import Anthropic from '@anthropic-ai/sdk'

const MODEL = 'claude-haiku-4-5' // matches the project's chatbot model (core/ai.py AI_MODEL)

function send(res, status, body) {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify(body))
}

function readJsonBody(req) {
  return new Promise((resolve) => {
    if (req.body) return resolve(typeof req.body === 'string' ? JSON.parse(req.body) : req.body)
    let data = ''
    req.on('data', (c) => (data += c))
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {})
      } catch {
        resolve({})
      }
    })
  })
}

async function loadData(origin, file) {
  try {
    const r = await fetch(`${origin}/data/${file}.json`)
    return r.ok ? await r.json() : null
  } catch {
    return null
  }
}

// Build the grounding block from real data — the only numbers the model may cite.
export function buildContext(predictions, players, matchLab) {
  const lines = []
  if (predictions?.champions?.length) {
    lines.push(
      'Predicted champion probability (our model, Monte-Carlo over the knockout bracket): ' +
        predictions.champions.map((c) => `${c.name} ${c.v}%`).join(', ') + '.',
    )
  }
  if (players?.players?.length) {
    const top = players.players.slice(0, 5)
    lines.push('Golden Boot race (goals): ' + top.map((p) => `${p.name} ${p.goals}`).join(', ') + '.')
    const byXg = [...players.players].sort((a, b) => b.xg - a.xg).slice(0, 4)
    lines.push('Highest xG: ' + byXg.map((p) => `${p.name} ${p.xg.toFixed(1)}`).join(', ') + '.')
  }
  const b = predictions?.bracket
  if (b) {
    const r16done = (b.r16 || []).filter((m) => m.done)
    if (r16done.length) {
      lines.push('Round of 16 results so far: ' + r16done.map((m) => `${m.home.code} ${m.sh}-${m.sa} ${m.away.code}`).join(', ') + '.')
    }
    const r16pick = (b.r16 || []).filter((m) => !m.done)
    if (r16pick.length) {
      lines.push('Confirmed Round of 16 ties still to play, with our pick: ' +
        r16pick.map((m) => `${m.home.code} v ${m.away.code} (${m.favHome ? m.home.code : m.away.code} ${m.prob}%)`).join(', ') + '.')
    }
    if (b.final) {
      lines.push(`Our projected final: ${b.final.home.code} v ${b.final.away.code}, predicted champion ${b.final.champion || (b.final.favHome ? b.final.home.name : b.final.away.name)} (${b.final.prob}%).`)
    }
  }
  if (predictions?.nextMatch) {
    const nm = predictions.nextMatch
    lines.push(`Next match: ${nm.home.name} v ${nm.away.name} (${nm.round}, ${nm.date}), our pick ${nm.favCode} ${nm.prob}%.`)
  }
  if (matchLab) {
    const s = matchLab.stats || {}
    const p = (k) => (s[k] || [null, null])
    const scorers = (matchLab.timeline || []).filter((e) => e.type === 'g').map((e) => `${e.player} ${e.min}'`).join(', ')
    lines.push(
      `\nThe user is currently viewing this match in Match Lab — ground answers about 'this match/game' in it: ` +
        `${matchLab.home.name} ${matchLab.score[0]}-${matchLab.score[1]} ${matchLab.away.name} (${matchLab.round}, ${matchLab.date}). ` +
        `Possession ${p('possession')[0]}%-${p('possession')[1]}%, xG ${p('xg')[0]}-${p('xg')[1]}, shots ${p('shots')[0]}-${p('shots')[1]} ` +
        `(on target ${p('sot')[0]}-${p('sot')[1]}). Scorers: ${scorers || 'none'}.`,
    )
  }
  return lines.join('\n')
}

const SYSTEM_BASE =
  'You are Parker, an elite football analytics AI for the 2026 FIFA World Cup (hosts: USA, Canada, Mexico). ' +
  'The tournament is at the knockout stage. Answer in 2-4 crisp, confident sentences like a top data scientist. ' +
  'Give a clear prediction when asked. Plain text only — no markdown, no bullet points, no headings. ' +
  'CRITICAL: only cite numbers that appear in the model snapshot below. Never invent stats, scores, xG or ' +
  'probabilities. If the snapshot does not contain a number the user asks for, say what the model does show ' +
  'instead — do not guess.'

const FALLBACK =
  "Parker's live engine isn't reachable right now, but the model has France as the clear title favourite, with Spain, Morocco and Argentina its next most-likely champions. Open the dashboard to explore the full bracket."

export default async function handler(req, res) {
  // Safe health check: reports only whether the key is visible (never its value).
  if (req.method === 'GET') {
    const k = process.env.ANTHROPIC_API_KEY || ''
    const base = { ok: true, hasKey: k.length > 0, keyLooksValid: k.startsWith('sk-ant-'), keyLen: k.length, model: MODEL }
    if ((req.url || '').includes('test=1') && k) {
      try {
        const client = new Anthropic({ apiKey: k })
        const r = await client.messages.create({ model: MODEL, max_tokens: 16, messages: [{ role: 'user', content: 'ping' }] })
        return send(res, 200, { ...base, testOk: true, respModel: r.model })
      } catch (e) {
        return send(res, 200, { ...base, testOk: false, errStatus: e && e.status, errType: e && e.name, errMsg: String(e && e.message).slice(0, 300) })
      }
    }
    return send(res, 200, base)
  }
  if (req.method !== 'POST') return send(res, 405, { error: 'method not allowed' })
  const body = await readJsonBody(req)
  const { messages = [], view, matchId } = body
  const userTurns = messages.filter((m) => m && m.role === 'user' && m.content)
  if (!userTurns.length) return send(res, 400, { error: 'no message' })

  const key = process.env.ANTHROPIC_API_KEY
  if (!key) return send(res, 200, { text: FALLBACK, grounded: false })

  const origin = `${(req.headers['x-forwarded-proto'] || 'http')}://${req.headers.host}`
  const [predictions, players] = await Promise.all([loadData(origin, 'predictions'), loadData(origin, 'players')])
  let matchLab = null
  if (view === 'matchlab') {
    const matches = await loadData(origin, 'matches')
    matchLab = (matches || []).find((m) => m.id === matchId) || (matches || [])[0] || null
  }

  const context = buildContext(predictions, players, matchLab)
  const system = SYSTEM_BASE + '\n\nModel snapshot (reference these figures naturally, never dump them verbatim):\n' + context

  try {
    const client = new Anthropic({ apiKey: key })
    const resp = await client.messages.create({
      model: MODEL,
      max_tokens: 400,
      system,
      messages: messages.slice(-6).map((m) => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.content })),
    })
    const text = (resp.content || []).filter((b) => b.type === 'text').map((b) => b.text).join('').trim()
    return send(res, 200, { text: text || FALLBACK, grounded: true })
  } catch (e) {
    return send(res, 200, { text: FALLBACK, grounded: false, error: String(e && e.message) })
  }
}
