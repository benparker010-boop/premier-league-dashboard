/*
  FIFA 3-letter code -> ISO 3166-1 alpha-2 (or, for the UK home nations, the
  flagcdn subdivision code) for every team in this tournament (see CODES in
  web/scripts/build_data.py — keep in sync if the team list ever changes).
  Used to fetch real national flags from flagcdn.com instead of the old
  hashed colour swatch.
*/
export const ISO2 = {
  ALG: 'dz', ARG: 'ar', AUS: 'au', AUT: 'at', BEL: 'be', BIH: 'ba', BRA: 'br',
  CAN: 'ca', CPV: 'cv', COL: 'co', CRO: 'hr', CUW: 'cw', CZE: 'cz', CIV: 'ci',
  COD: 'cd', ECU: 'ec', EGY: 'eg', ENG: 'gb-eng', FRA: 'fr', GER: 'de', GHA: 'gh',
  HAI: 'ht', IRN: 'ir', IRQ: 'iq', JPN: 'jp', JOR: 'jo', MEX: 'mx', MAR: 'ma',
  NED: 'nl', NZL: 'nz', NOR: 'no', PAN: 'pa', PAR: 'py', POR: 'pt', QAT: 'qa',
  KSA: 'sa', SCO: 'gb-sct', SEN: 'sn', RSA: 'za', KOR: 'kr', ESP: 'es', SWE: 'se',
  SUI: 'ch', TUN: 'tn', TUR: 'tr', USA: 'us', URU: 'uy', UZB: 'uz',
}

export function flagUrl(code) {
  const iso = ISO2[code]
  return iso ? `https://flagcdn.com/${iso}.svg` : null
}
