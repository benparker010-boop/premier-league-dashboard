/* Phase 2 placeholder data ported from the Parker.dc.html prototype
   (B_R16, B_QF, B_SF, B_F, GROUPS_DATA, NAT_ROSTERS, CHAMP, etc.).
   Replaced with the real API + core/predict.py output in Phase 4. */

export const SUGGESTIONS = [
  "Who's most likely to win the World Cup?",
  'Predict the final',
  'Best xG in the tournament?',
  'Who wins the Golden Boot?',
  'Argentina vs Spain — who advances?',
]

export const CHAMPIONS = [
  { code: 'FRA', name: 'France', v: 18.4, color: '#5b8cff' },
  { code: 'ARG', name: 'Argentina', v: 16.1, color: '#5ec8e0' },
  { code: 'ENG', name: 'England', v: 13.7, color: '#e8475e' },
  { code: 'BRA', name: 'Brazil', v: 12.9, color: '#f5c451' },
  { code: 'ESP', name: 'Spain', v: 11.2, color: '#ef7d52' },
  { code: 'POR', name: 'Portugal', v: 8.5, color: '#1faf6b' },
]

export const B_R16 = [
  { home: { code: 'FRA', color: '#5b8cff' }, away: { code: 'POL', color: '#e8475e' }, sh: 3, sa: 1, done: true, winner: 'home', prob: 67, label: 'R16 · M1' },
  { home: { code: 'ARG', color: '#5ec8e0' }, away: { code: 'AUS', color: '#f5c451' }, sh: 2, sa: 0, done: true, winner: 'home', prob: 72, label: 'R16 · M2' },
  { home: { code: 'ENG', color: '#e8475e' }, away: { code: 'SEN', color: '#1faf6b' }, sh: 3, sa: 0, done: true, winner: 'home', prob: 71, label: 'R16 · M3' },
  { home: { code: 'BRA', color: '#f5c451' }, away: { code: 'KOR', color: '#5b8cff' }, sh: 4, sa: 1, done: true, winner: 'home', prob: 76, label: 'R16 · M4' },
  { home: { code: 'GER', color: '#c3cfdc' }, away: { code: 'JPN', color: '#e8475e' }, sh: 2, sa: 1, done: true, winner: 'home', prob: 61, label: 'R16 · M5' },
  { home: { code: 'ESP', color: '#ef7d52' }, away: { code: 'MAR', color: '#2ecc71' }, sh: 1, sa: 0, done: true, winner: 'home', prob: 63, label: 'R16 · M6' },
  { home: { code: 'POR', color: '#1faf6b' }, away: { code: 'CHE', color: '#e8475e' }, sh: 6, sa: 1, done: true, winner: 'home', prob: 58, label: 'R16 · M7' },
  { home: { code: 'NED', color: '#ef7d52' }, away: { code: 'USA', color: '#5b8cff' }, sh: 3, sa: 1, done: true, winner: 'home', prob: 54, label: 'R16 · M8' },
]

export const B_QF = [
  { home: { code: 'FRA', color: '#5b8cff' }, away: { code: 'ARG', color: '#5ec8e0' }, sh: '–', sa: '–', done: false, winner: null, prob: 58, label: 'QF · Jul 4', date: 'Jul 4', venue: 'MetLife Stadium, NJ' },
  { home: { code: 'ENG', color: '#e8475e' }, away: { code: 'BRA', color: '#f5c451' }, sh: '–', sa: '–', done: false, winner: null, prob: 42, label: 'QF · Jul 5', date: 'Jul 5', venue: 'AT&T Stadium, Dallas' },
  { home: { code: 'GER', color: '#c3cfdc' }, away: { code: 'ESP', color: '#ef7d52' }, sh: '–', sa: '–', done: false, winner: null, prob: 44, label: 'QF · Jul 6', date: 'Jul 6', venue: 'SoFi Stadium, LA' },
  { home: { code: 'POR', color: '#1faf6b' }, away: { code: 'NED', color: '#ef7d52' }, sh: '–', sa: '–', done: false, winner: null, prob: 54, label: 'QF · Jul 7', date: 'Jul 7', venue: 'Mercedes-Benz Stadium, ATL' },
]

export const B_SF = [
  { home: { code: 'FRA', color: '#5b8cff' }, away: { code: 'BRA', color: '#f5c451' }, sh: '–', sa: '–', done: false, winner: null, prob: 60, label: 'SF · Jul 11', date: 'Jul 11', venue: 'MetLife Stadium, NJ' },
  { home: { code: 'ESP', color: '#ef7d52' }, away: { code: 'POR', color: '#1faf6b' }, sh: '–', sa: '–', done: false, winner: null, prob: 56, label: 'SF · Jul 12', date: 'Jul 12', venue: 'AT&T Stadium, Dallas' },
]

export const B_F = { home: { code: 'FRA', color: '#5b8cff' }, away: { code: 'ESP', color: '#ef7d52' }, sh: '–', sa: '–', done: false, winner: null, prob: 63, label: 'FINAL', date: 'Jul 19', venue: 'MetLife Stadium, NJ' }

export const B_R16_DATES = ['Jun 28', 'Jun 28', 'Jun 28', 'Jun 28', 'Jun 29', 'Jun 29', 'Jun 29', 'Jun 29']
export const B_R16_VENUES = ['SoFi Stadium, LA', 'AT&T Stadium, Dallas', 'Mercedes-Benz Stadium, ATL', 'MetLife Stadium, NJ', 'Lincoln Financial Field, PHL', "Levi's Stadium, SF", 'Estadio Azteca, MEX', 'BC Place, Vancouver']

export const NEXT_MATCH = {
  round: 'QUARTER-FINAL', date: 'Fri, Jul 4', time: '3:00 PM ET', venue: 'MetLife Stadium, NJ',
  home: { code: 'FRA', name: 'France', color: '#5b8cff' }, away: { code: 'ARG', name: 'Argentina', color: '#5ec8e0' }, prob: 58,
}

export const LAST_MATCH = {
  round: 'ROUND OF 16', date: 'Mon, Jun 29', venue: 'AT&T Stadium, Dallas, TX',
  home: { code: 'NED', name: 'Netherlands', color: '#ef7d52' }, away: { code: 'USA', name: 'USA', color: '#5b8cff' },
  sh: 3, sa: 1, scorers: 'Gakpo 23′, Depay 41′, 78′ · Pulisic 65′',
}

export const GROUPS_DATA = [
  { name: 'A', teams: [{ code: 'FRA', color: '#5b8cff', p: 3, w: 2, d: 1, l: 0, gf: 7, ga: 2, gd: 5, pts: 7, qual: 'q1' }, { code: 'POL', color: '#e8475e', p: 3, w: 1, d: 1, l: 1, gf: 3, ga: 4, gd: -1, pts: 4, qual: 'q2' }, { code: 'MEX', color: '#2ecc71', p: 3, w: 0, d: 1, l: 2, gf: 2, ga: 5, gd: -3, pts: 1, qual: 'x' }, { code: 'ISL', color: '#9fb0c2', p: 3, w: 0, d: 1, l: 2, gf: 1, ga: 3, gd: -2, pts: 1, qual: 'x' }] },
  { name: 'B', teams: [{ code: 'ARG', color: '#5ec8e0', p: 3, w: 2, d: 1, l: 0, gf: 7, ga: 1, gd: 6, pts: 7, qual: 'q1' }, { code: 'DEN', color: '#e8475e', p: 3, w: 1, d: 1, l: 1, gf: 4, ga: 4, gd: 0, pts: 4, qual: 'q2' }, { code: 'KSA', color: '#1faf6b', p: 3, w: 1, d: 0, l: 2, gf: 2, ga: 5, gd: -3, pts: 3, qual: 'x' }, { code: 'TUN', color: '#ef7d52', p: 3, w: 0, d: 0, l: 3, gf: 1, ga: 4, gd: -3, pts: 0, qual: 'x' }] },
  { name: 'C', teams: [{ code: 'ENG', color: '#e8475e', p: 3, w: 2, d: 1, l: 0, gf: 8, ga: 3, gd: 5, pts: 7, qual: 'q1' }, { code: 'USA', color: '#5b8cff', p: 3, w: 1, d: 1, l: 1, gf: 4, ga: 4, gd: 0, pts: 4, qual: 'q2' }, { code: 'IRN', color: '#1faf6b', p: 3, w: 0, d: 2, l: 1, gf: 2, ga: 4, gd: -2, pts: 2, qual: 'x' }, { code: 'WAL', color: '#c3cfdc', p: 3, w: 0, d: 0, l: 3, gf: 1, ga: 4, gd: -3, pts: 0, qual: 'x' }] },
  { name: 'D', teams: [{ code: 'BRA', color: '#f5c451', p: 3, w: 3, d: 0, l: 0, gf: 9, ga: 2, gd: 7, pts: 9, qual: 'q1' }, { code: 'KOR', color: '#5b8cff', p: 3, w: 1, d: 1, l: 1, gf: 3, ga: 5, gd: -2, pts: 4, qual: 'q2' }, { code: 'SRB', color: '#e8475e', p: 3, w: 0, d: 2, l: 1, gf: 2, ga: 3, gd: -1, pts: 2, qual: 'x' }, { code: 'CMR', color: '#2ecc71', p: 3, w: 0, d: 1, l: 2, gf: 1, ga: 5, gd: -4, pts: 1, qual: 'x' }] },
  { name: 'E', teams: [{ code: 'GER', color: '#c3cfdc', p: 3, w: 2, d: 0, l: 1, gf: 6, ga: 3, gd: 3, pts: 6, qual: 'q1' }, { code: 'AUS', color: '#f5c451', p: 3, w: 1, d: 1, l: 1, gf: 4, ga: 4, gd: 0, pts: 4, qual: 'q2' }, { code: 'JPN', color: '#e8475e', p: 3, w: 1, d: 0, l: 2, gf: 3, ga: 5, gd: -2, pts: 3, qual: 'x' }, { code: 'CRC', color: '#2ecc71', p: 3, w: 0, d: 1, l: 2, gf: 1, ga: 2, gd: -1, pts: 1, qual: 'x' }] },
  { name: 'F', teams: [{ code: 'ESP', color: '#ef7d52', p: 3, w: 2, d: 1, l: 0, gf: 7, ga: 2, gd: 5, pts: 7, qual: 'q1' }, { code: 'MAR', color: '#2ecc71', p: 3, w: 1, d: 1, l: 1, gf: 3, ga: 3, gd: 0, pts: 4, qual: 'q2' }, { code: 'CHI', color: '#e8475e', p: 3, w: 1, d: 0, l: 2, gf: 2, ga: 4, gd: -2, pts: 3, qual: 'x' }, { code: 'NZL', color: '#9fb0c2', p: 3, w: 0, d: 0, l: 3, gf: 0, ga: 3, gd: -3, pts: 0, qual: 'x' }] },
  { name: 'G', teams: [{ code: 'POR', color: '#1faf6b', p: 3, w: 3, d: 0, l: 0, gf: 9, ga: 1, gd: 8, pts: 9, qual: 'q1' }, { code: 'CHE', color: '#e8475e', p: 3, w: 1, d: 0, l: 2, gf: 3, ga: 6, gd: -3, pts: 3, qual: 'q2' }, { code: 'NGA', color: '#2ecc71', p: 3, w: 1, d: 0, l: 2, gf: 2, ga: 5, gd: -3, pts: 3, qual: 'x' }, { code: 'QAT', color: '#9d5fb5', p: 3, w: 0, d: 0, l: 3, gf: 1, ga: 3, gd: -2, pts: 0, qual: 'x' }] },
  { name: 'H', teams: [{ code: 'NED', color: '#ef7d52', p: 3, w: 2, d: 1, l: 0, gf: 6, ga: 2, gd: 4, pts: 7, qual: 'q1' }, { code: 'BEL', color: '#e8475e', p: 3, w: 1, d: 1, l: 1, gf: 4, ga: 3, gd: 1, pts: 4, qual: 'q2' }, { code: 'ECU', color: '#f5c451', p: 3, w: 1, d: 0, l: 2, gf: 2, ga: 4, gd: -2, pts: 3, qual: 'x' }, { code: 'ALB', color: '#c3cfdc', p: 3, w: 0, d: 0, l: 3, gf: 1, ga: 4, gd: -3, pts: 0, qual: 'x' }] },
  { name: 'I', teams: [{ code: 'COL', color: '#f5c451', p: 3, w: 2, d: 0, l: 1, gf: 5, ga: 3, gd: 2, pts: 6, qual: 'q1' }, { code: 'SEN', color: '#2ecc71', p: 3, w: 1, d: 1, l: 1, gf: 4, ga: 4, gd: 0, pts: 4, qual: 'q2' }, { code: 'URU', color: '#5b8cff', p: 3, w: 1, d: 0, l: 2, gf: 4, ga: 5, gd: -1, pts: 3, qual: 'x' }, { code: 'IRQ', color: '#2ecc71', p: 3, w: 0, d: 1, l: 2, gf: 1, ga: 2, gd: -1, pts: 1, qual: 'x' }] },
  { name: 'J', teams: [{ code: 'ITA', color: '#5b8cff', p: 3, w: 1, d: 2, l: 0, gf: 5, ga: 3, gd: 2, pts: 5, qual: 'q1' }, { code: 'CRO', color: '#e8475e', p: 3, w: 1, d: 1, l: 1, gf: 4, ga: 4, gd: 0, pts: 4, qual: 'q2' }, { code: 'ALG', color: '#2ecc71', p: 3, w: 0, d: 2, l: 1, gf: 2, ga: 3, gd: -1, pts: 2, qual: 'x' }, { code: 'CGO', color: '#9fb0c2', p: 3, w: 0, d: 1, l: 2, gf: 1, ga: 2, gd: -1, pts: 1, qual: 'x' }] },
  { name: 'K', teams: [{ code: 'CAN', color: '#e8475e', p: 3, w: 1, d: 2, l: 0, gf: 3, ga: 1, gd: 2, pts: 5, qual: 'q1' }, { code: 'JAM', color: '#f5c451', p: 3, w: 1, d: 1, l: 1, gf: 2, ga: 2, gd: 0, pts: 4, qual: 'q2' }, { code: 'HON', color: '#5b8cff', p: 3, w: 0, d: 2, l: 1, gf: 1, ga: 2, gd: -1, pts: 2, qual: 'x' }, { code: 'EGY', color: '#ef7d52', p: 3, w: 0, d: 1, l: 2, gf: 1, ga: 2, gd: -1, pts: 1, qual: 'x' }] },
  { name: 'L', teams: [{ code: 'TUR', color: '#e8475e', p: 3, w: 2, d: 0, l: 1, gf: 5, ga: 4, gd: 1, pts: 6, qual: 'q1' }, { code: 'GHA', color: '#f5c451', p: 3, w: 1, d: 1, l: 1, gf: 3, ga: 3, gd: 0, pts: 4, qual: 'q2' }, { code: 'GRE', color: '#5b8cff', p: 3, w: 1, d: 0, l: 2, gf: 2, ga: 3, gd: -1, pts: 3, qual: 'x' }, { code: 'UZB', color: '#2ecc71', p: 3, w: 0, d: 1, l: 2, gf: 1, ga: 1, gd: 0, pts: 1, qual: 'x' }] },
]

// [code, color, nation, [[name, goals, xg, assists, yellows], ...]]
const NAT_ROSTERS = [
  ['FRA', '#5b8cff', 'France', [['K. Mbappé', 6, 5.4, 3, 1], ['A. Griezmann', 2, 2.1, 4, 0]]],
  ['POL', '#e8475e', 'Poland', [['R. Lewandowski', 3, 3.1, 1, 0], ['P. Zieliński', 1, 1.0, 2, 1]]],
  ['MEX', '#2ecc71', 'Mexico', [['S. Giménez', 2, 1.8, 1, 0], ['E. Álvarez', 1, 0.9, 2, 0]]],
  ['ISL', '#9fb0c2', 'Iceland', [['A. Gudmundsson', 1, 1.1, 0, 1], ['G. Sigurdsson', 0, 0.6, 1, 0]]],
  ['ARG', '#5ec8e0', 'Argentina', [['L. Messi', 3, 2.9, 5, 0], ['J. Álvarez', 5, 3.9, 1, 1]]],
  ['DEN', '#e8475e', 'Denmark', [['R. Højlund', 2, 2.3, 0, 1], ['C. Eriksen', 1, 1.2, 3, 0]]],
  ['KSA', '#1faf6b', 'Saudi Arabia', [['S. Al-Dawsari', 1, 1.0, 1, 0], ['F. Al-Buraikan', 1, 0.8, 0, 1]]],
  ['TUN', '#ef7d52', 'Tunisia', [['Y. Msakni', 0, 0.7, 1, 0], ['I. Khazri', 1, 0.9, 0, 1]]],
  ['ENG', '#e8475e', 'England', [['H. Kane', 5, 4.8, 2, 0], ['P. Foden', 2, 1.8, 4, 0]]],
  ['USA', '#5b8cff', 'USA', [['C. Pulisic', 2, 2.0, 1, 0], ['F. Balogun', 1, 1.4, 0, 0]]],
  ['IRN', '#1faf6b', 'Iran', [['M. Taremi', 2, 1.9, 0, 1], ['S. Azmoun', 1, 1.0, 1, 0]]],
  ['WAL', '#c3cfdc', 'Wales', [['D. James', 0, 0.6, 1, 0], ['K. Moore', 0, 0.5, 0, 1]]],
  ['BRA', '#f5c451', 'Brazil', [['Vinícius Jr', 4, 3.2, 4, 2], ['Rodrygo', 2, 1.9, 2, 0]]],
  ['KOR', '#5b8cff', 'S. Korea', [['Son Heung-min', 2, 2.2, 1, 0], ['Lee Kang-in', 1, 0.9, 2, 0]]],
  ['SRB', '#e8475e', 'Serbia', [['D. Vlahović', 2, 2.4, 0, 1], ['A. Mitrović', 1, 1.6, 0, 0]]],
  ['CMR', '#2ecc71', 'Cameroon', [['B. Aboubakar', 1, 1.0, 0, 0], ['K. Ntcham', 0, 0.5, 1, 0]]],
  ['GER', '#c3cfdc', 'Germany', [['K. Havertz', 3, 2.7, 2, 1], ['F. Wirtz', 2, 2.0, 3, 0]]],
  ['AUS', '#f5c451', 'Australia', [['M. Boyle', 1, 0.8, 1, 0], ['C. Goodwin', 1, 0.9, 0, 0]]],
  ['JPN', '#e8475e', 'Japan', [['T. Kubo', 2, 1.7, 1, 0], ['K. Mitoma', 1, 1.2, 2, 0]]],
  ['CRC', '#2ecc71', 'Costa Rica', [['J. Campbell', 1, 0.7, 0, 0], ['A. Contreras', 0, 0.4, 1, 0]]],
  ['ESP', '#ef7d52', 'Spain', [['L. Yamal', 4, 2.8, 5, 0], ['Á. Morata', 2, 2.1, 1, 1]]],
  ['MAR', '#2ecc71', 'Morocco', [['A. Hakimi', 1, 0.9, 2, 0], ['Y. En-Nesyri', 2, 2.0, 0, 0]]],
  ['CHI', '#e8475e', 'Chile', [['A. Vidal', 0, 0.5, 1, 1], ['A. Sánchez', 1, 1.1, 0, 0]]],
  ['NZL', '#9fb0c2', 'New Zealand', [['C. Wood', 1, 1.3, 0, 0], ['M. Boxall', 0, 0.3, 0, 1]]],
  ['POR', '#1faf6b', 'Portugal', [['C. Ronaldo', 4, 3.6, 0, 1], ['B. Fernandes', 2, 2.9, 4, 1]]],
  ['CHE', '#e8475e', 'Switzerland', [['B. Embolo', 1, 1.2, 0, 0], ['X. Shaqiri', 1, 0.9, 1, 0]]],
  ['NGA', '#2ecc71', 'Nigeria', [['V. Osimhen', 2, 2.3, 0, 1], ['A. Lookman', 1, 1.4, 1, 0]]],
  ['QAT', '#9d5fb5', 'Qatar', [['A. Afif', 1, 0.8, 0, 0], ['Almoez Ali', 1, 1.0, 0, 1]]],
  ['NED', '#ef7d52', 'Netherlands', [['C. Gakpo', 2, 2.1, 1, 0], ['M. Depay', 1, 1.5, 2, 1]]],
  ['BEL', '#e8475e', 'Belgium', [['K. De Bruyne', 1, 1.6, 4, 0], ['R. Lukaku', 2, 2.4, 0, 0]]],
  ['ECU', '#f5c451', 'Ecuador', [['E. Valencia', 1, 1.1, 0, 0], ['M. Caicedo', 0, 0.5, 1, 1]]],
  ['ALB', '#c3cfdc', 'Albania', [['A. Broja', 1, 0.9, 0, 0], ['N. Bajrami', 0, 0.4, 1, 0]]],
  ['COL', '#f5c451', 'Colombia', [['J. Rodríguez', 2, 1.8, 3, 0], ['R. Díaz', 3, 2.2, 1, 1]]],
  ['SEN', '#2ecc71', 'Senegal', [['A. Diallo', 3, 2.4, 3, 0], ['S. Mané', 2, 1.9, 1, 0]]],
  ['URU', '#5b8cff', 'Uruguay', [['D. Núñez', 2, 2.1, 0, 1], ['F. Valverde', 1, 1.3, 2, 0]]],
  ['IRQ', '#2ecc71', 'Iraq', [['A. Yaseen', 1, 0.9, 0, 0], ['M. Basil', 0, 0.6, 1, 0]]],
  ['ITA', '#5b8cff', 'Italy', [['F. Chiesa', 2, 1.9, 1, 0], ['G. Scamacca', 1, 1.5, 0, 1]]],
  ['CRO', '#e8475e', 'Croatia', [['L. Modrić', 1, 1.0, 3, 0], ['A. Budimir', 1, 1.2, 0, 0]]],
  ['ALG', '#2ecc71', 'Algeria', [['R. Mahrez', 1, 1.1, 1, 0], ['Y. Belaïli', 0, 0.6, 1, 0]]],
  ['CGO', '#9fb0c2', 'Congo DR', [['C. Bakambu', 1, 1.0, 0, 1], ['M. Bushiri', 0, 0.4, 0, 0]]],
  ['CAN', '#e8475e', 'Canada', [['A. Davies', 1, 0.9, 2, 0], ['J. David', 2, 2.0, 0, 0]]],
  ['JAM', '#f5c451', 'Jamaica', [['L. Blackwood', 0, 0.4, 0, 1], ['B. Nicholson', 1, 0.7, 1, 0]]],
  ['HON', '#5b8cff', 'Honduras', [['R. Elis', 0, 0.5, 0, 0], ['A. López', 0, 0.4, 1, 0]]],
  ['EGY', '#ef7d52', 'Egypt', [['M. Salah', 3, 2.6, 1, 0], ['O. Marmoush', 1, 1.3, 0, 1]]],
  ['TUR', '#e8475e', 'Turkey', [['A. Güler', 2, 1.7, 2, 0], ['K. Yıldız', 1, 1.1, 1, 0]]],
  ['GHA', '#f5c451', 'Ghana', [['M. Kudus', 2, 2.0, 1, 0], ['T. Partey', 0, 0.6, 0, 1]]],
  ['GRE', '#5b8cff', 'Greece', [['F. Masouras', 0, 0.5, 0, 0], ['G. Baldock', 0, 0.3, 1, 0]]],
  ['UZB', '#2ecc71', 'Uzbekistan', [['E. Shomurodov', 1, 1.0, 0, 0], ['A. Sadikov', 0, 0.4, 0, 1]]],
]

export const PLAYERS_DATA = NAT_ROSTERS.flatMap(([code, color, nation, ps]) =>
  ps.map((p) => ({ name: p[0], code, color, nation, goals: p[1], xg: p[2], assists: p[3], yc: p[4] })),
)

export const TICKER_RESULTS = 'ARG 2–1 AUS · FRA 3–0 NGA · ENG 1–1 ECU · BRA 2–0 KSA · ESP 4–1 JPN · NED 1–0 MEX · POR 2–2 USA · GER 3–1 CRO'
export const TICKER_R16 = 'FRA v POR · Jul 1 · ARG v ESP · Jul 2 · ENG v NED · Jul 2 · BRA v GER · Jul 3'
