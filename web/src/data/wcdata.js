/* Parker — World Cup 2026 placeholder dataset (Phase 2), ported from
   design_handoff/wcdata.js. Shaped to mirror the real TheStatsAPI fields
   (ball_possession, expected_goals, total_shots, timeline goal events,
   lineups) so it can be swapped for a live feed in Phase 4. */

// formation templates: d = depth 0(GK)..1(forward), w = width 0(left)..1(right)
export const FORMATIONS = {
  '4-3-3': [
    { pos: 'GK', d: 0, w: 0.5 },
    { pos: 'RB', d: 0.16, w: 0.86 }, { pos: 'CB', d: 0.1, w: 0.64 }, { pos: 'CB', d: 0.1, w: 0.36 }, { pos: 'LB', d: 0.16, w: 0.14 },
    { pos: 'CM', d: 0.44, w: 0.7 }, { pos: 'CM', d: 0.36, w: 0.5 }, { pos: 'CM', d: 0.44, w: 0.3 },
    { pos: 'RW', d: 0.75, w: 0.84 }, { pos: 'ST', d: 0.83, w: 0.5 }, { pos: 'LW', d: 0.75, w: 0.16 },
  ],
  '4-2-3-1': [
    { pos: 'GK', d: 0, w: 0.5 },
    { pos: 'RB', d: 0.16, w: 0.86 }, { pos: 'CB', d: 0.1, w: 0.64 }, { pos: 'CB', d: 0.1, w: 0.36 }, { pos: 'LB', d: 0.16, w: 0.14 },
    { pos: 'DM', d: 0.34, w: 0.62 }, { pos: 'DM', d: 0.34, w: 0.38 },
    { pos: 'RW', d: 0.66, w: 0.84 }, { pos: 'AM', d: 0.62, w: 0.5 }, { pos: 'LW', d: 0.66, w: 0.16 },
    { pos: 'ST', d: 0.85, w: 0.5 },
  ],
}

export const TEAMS = {
  ESP: { name: 'Spain', color: '#ef7d52', formation: '4-3-3', xi: ['Simón', 'Carvajal', 'Le Normand', 'Laporte', 'Cucurella', 'Pedri', 'Rodri', 'F. Ruiz', 'Yamal', 'Morata', 'N. Williams'], subs: ['Oyarzabal', 'Olmo', 'Merino', 'F. Torres', 'Zubimendi'] },
  JPN: { name: 'Japan', color: '#4f7bd6', formation: '4-2-3-1', xi: ['Suzuki', 'Sugawara', 'Itakura', 'Tomiyasu', 'Nakayama', 'Endō', 'Morita', 'Dōan', 'Kamada', 'Mitoma', 'Ueda'], subs: ['Asano', 'Kubo', 'Minamino', 'Tanaka', 'Maeda'] },
  FRA: { name: 'France', color: '#5b8cff', formation: '4-3-3', xi: ['Maignan', 'Koundé', 'Saliba', 'Upamecano', 'T. Hernández', 'Tchouaméni', 'Camavinga', 'Griezmann', 'Dembélé', 'Mbappé', 'Barcola'], subs: ['Giroud', 'Coman', 'Thuram', 'Zaïre-Emery', 'Kanté'] },
  NGA: { name: 'Nigeria', color: '#2faf6b', formation: '4-3-3', xi: ['Nwabali', 'Aina', 'Bassey', 'Ekong', 'Sanusi', 'Onyedika', 'Ndidi', 'Iwobi', 'Lookman', 'Osimhen', 'Chukwueze'], subs: ['Moffi', 'Boniface', 'Aribo', 'Simon', 'Onyeka'] },
  ARG: { name: 'Argentina', color: '#5ec8e0', formation: '4-3-3', xi: ['E. Martínez', 'Molina', 'Romero', 'Otamendi', 'Tagliafico', 'De Paul', 'Mac Allister', 'Fernández', 'Messi', 'J. Álvarez', 'Di María'], subs: ['L. Martínez', 'N. González', 'Paredes', 'Garnacho', 'Lo Celso'] },
  AUS: { name: 'Australia', color: '#e0a93b', formation: '4-2-3-1', xi: ['Ryan', 'Atkinson', 'Souttar', 'Rowles', 'Behich', 'Irvine', 'Metcalfe', 'Leckie', 'McGree', 'Goodwin', 'Duke'], subs: ['Boyle', 'Maclaren', 'Tilio', 'Baccus', 'Yengi'] },
  BRA: { name: 'Brazil', color: '#f5c451', formation: '4-2-3-1', xi: ['Alisson', 'Danilo', 'Marquinhos', 'G. Magalhães', 'Wendell', 'Bruno G.', 'André', 'Raphinha', 'Rodrygo', 'Vinícius Jr', 'Endrick'], subs: ['Martinelli', 'Paquetá', 'Savinho', 'G. Jesus', 'Bremer'] },
  KSA: { name: 'Saudi Arabia', color: '#1f9e63', formation: '4-2-3-1', xi: ['Al-Owais', 'Al-Ghannam', 'Al-Amri', 'Al-Bulaihi', 'Al-Shahrani', 'Al-Faraj', 'Kanno', 'Al-Dawsari', 'Al-Buraikan', 'Al-Shehri', 'Al-Brikan'], subs: ['Al-Ghamdi', 'Asiri', 'Al-Najei', 'Bahebri', 'Al-Hassan'] },
  GER: { name: 'Germany', color: '#c9ced4', formation: '4-2-3-1', xi: ['Neuer', 'Kimmich', 'Tah', 'Rüdiger', 'Mittelstädt', 'Andrich', 'Groß', 'Sané', 'Wirtz', 'Musiala', 'Havertz'], subs: ['Füllkrug', 'Undav', 'Can', 'Gündoğan', 'Adeyemi'] },
  CRO: { name: 'Croatia', color: '#e8475e', formation: '4-3-3', xi: ['Livaković', 'Stanišić', 'Šutalo', 'Gvardiol', 'Sosa', 'Modrić', 'Brozović', 'Kovačić', 'Pašalić', 'Budimir', 'Perišić'], subs: ['Kramarić', 'Petković', 'Majer', 'Baturina', 'Sučić'] },
  ENG: { name: 'England', color: '#e85e7a', formation: '4-2-3-1', xi: ['Pickford', 'Walker', 'Stones', 'Guéhi', 'Trippier', 'Rice', 'Bellingham', 'Saka', 'Foden', 'Gordon', 'Kane'], subs: ['Watkins', 'Palmer', 'Mainoo', 'Toney', 'Gallagher'] },
  ECU: { name: 'Ecuador', color: '#efc24a', formation: '4-3-3', xi: ['Galíndez', 'Preciado', 'F. Torres', 'Hincapié', 'Estupiñán', 'Caicedo', 'Franco', 'Plata', 'Páez', 'E. Valencia', 'G. Rodríguez'], subs: ['Sarmiento', 'Mena', 'Cifuentes', 'Mercado', 'Reasco'] },
}

// shots: x 50..99 toward goal at right, y 8..92 width; outcome g=goal s=on-target o=off b=blocked
export const MATCHES = [
  {
    id: 'esp-jpn', home: 'ESP', away: 'JPN', score: [4, 1], ht: [2, 0], date: '24 Jun 2026', venue: 'Mercedes-Benz Stadium', city: 'Atlanta', ref: 'César Ramos', group: 'Group E',
    stats: { possession: [61, 39], xg: [3.1, 0.9], shots: [17, 8], sot: [8, 3], big: [5, 1], corners: [7, 3], fouls: [9, 12], yellow: [1, 2], red: [0, 0], passes: [612, 381], passAcc: [89, 82], tackles: [14, 18], saves: [2, 4] },
    timeline: [
      { min: 12, type: 'g', team: 'home', player: 'Morata', assist: 'Yamal' },
      { min: 34, type: 'g', team: 'home', player: 'Yamal', assist: 'Pedri' },
      { min: 40, type: 'y', team: 'away', player: 'Endō' },
      { min: 51, type: 'g', team: 'away', player: 'Mitoma' },
      { min: 58, type: 'y', team: 'away', player: 'Itakura' },
      { min: 63, type: 'g', team: 'home', player: 'N. Williams', assist: 'Pedri' },
      { min: 70, type: 'y', team: 'home', player: 'Rodri' },
      { min: 72, type: 's', team: 'home', player: 'Oyarzabal', detail: 'on' },
      { min: 77, type: 'g', team: 'home', player: 'Oyarzabal', assist: 'Olmo' },
    ],
    shots: [
      { team: 'home', min: 12, player: 'Morata', xg: 0.34, outcome: 'g', x: 88, y: 46 },
      { team: 'home', min: 34, player: 'Yamal', xg: 0.12, outcome: 'g', x: 74, y: 62 },
      { team: 'home', min: 28, player: 'Pedri', xg: 0.08, outcome: 's', x: 70, y: 50 },
      { team: 'home', min: 63, player: 'N. Williams', xg: 0.41, outcome: 'g', x: 90, y: 38 },
      { team: 'home', min: 77, player: 'Oyarzabal', xg: 0.55, outcome: 'g', x: 92, y: 52 },
      { team: 'home', min: 45, player: 'Morata', xg: 0.18, outcome: 'o', x: 80, y: 44 },
      { team: 'home', min: 69, player: 'Yamal', xg: 0.09, outcome: 'b', x: 72, y: 66 },
      { team: 'away', min: 51, player: 'Mitoma', xg: 0.22, outcome: 'g', x: 86, y: 58 },
      { team: 'away', min: 39, player: 'Ueda', xg: 0.14, outcome: 's', x: 82, y: 48 },
      { team: 'away', min: 66, player: 'Kubo', xg: 0.07, outcome: 'o', x: 74, y: 36 },
    ],
  },
  {
    id: 'fra-nga', home: 'FRA', away: 'NGA', score: [3, 0], ht: [1, 0], date: '23 Jun 2026', venue: 'MetLife Stadium', city: 'East Rutherford', ref: 'Szymon Marciniak', group: 'Group C',
    stats: { possession: [58, 42], xg: [2.6, 0.7], shots: [15, 6], sot: [7, 2], big: [4, 1], corners: [6, 2], fouls: [11, 10], yellow: [1, 1], red: [0, 0], passes: [574, 402], passAcc: [88, 81], tackles: [16, 15], saves: [2, 4] },
    timeline: [
      { min: 23, type: 'g', team: 'home', player: 'Mbappé', assist: 'Dembélé' },
      { min: 35, type: 'y', team: 'away', player: 'Ndidi' },
      { min: 59, type: 'g', team: 'home', player: 'Dembélé', assist: 'Griezmann' },
      { min: 74, type: 'y', team: 'home', player: 'Tchouaméni' },
      { min: 81, type: 'g', team: 'home', player: 'Griezmann', assist: 'Mbappé' },
    ],
    shots: [
      { team: 'home', min: 23, player: 'Mbappé', xg: 0.46, outcome: 'g', x: 90, y: 50 },
      { team: 'home', min: 59, player: 'Dembélé', xg: 0.21, outcome: 'g', x: 82, y: 60 },
      { team: 'home', min: 81, player: 'Griezmann', xg: 0.33, outcome: 'g', x: 86, y: 44 },
      { team: 'home', min: 40, player: 'Barcola', xg: 0.1, outcome: 's', x: 72, y: 64 },
      { team: 'home', min: 67, player: 'Mbappé', xg: 0.16, outcome: 'o', x: 78, y: 54 },
      { team: 'away', min: 48, player: 'Osimhen', xg: 0.27, outcome: 's', x: 84, y: 50 },
      { team: 'away', min: 71, player: 'Lookman', xg: 0.12, outcome: 'o', x: 74, y: 40 },
      { team: 'away', min: 55, player: 'Chukwueze', xg: 0.08, outcome: 'b', x: 70, y: 62 },
    ],
  },
  {
    id: 'arg-aus', home: 'ARG', away: 'AUS', score: [2, 1], ht: [1, 1], date: '22 Jun 2026', venue: 'AT&T Stadium', city: 'Arlington', ref: 'Anthony Taylor', group: 'Group A',
    stats: { possession: [64, 36], xg: [2.2, 0.9], shots: [16, 7], sot: [6, 3], big: [3, 1], corners: [8, 2], fouls: [8, 14], yellow: [1, 3], red: [0, 0], passes: [631, 352], passAcc: [90, 79], tackles: [12, 20], saves: [2, 4] },
    timeline: [
      { min: 18, type: 'g', team: 'home', player: 'J. Álvarez', assist: 'Messi' },
      { min: 39, type: 'g', team: 'away', player: 'Duke', assist: 'Goodwin' },
      { min: 44, type: 'y', team: 'away', player: 'Irvine' },
      { min: 61, type: 'y', team: 'away', player: 'Souttar' },
      { min: 74, type: 'g', team: 'home', player: 'Messi', assist: 'Mac Allister' },
      { min: 80, type: 'y', team: 'home', player: 'De Paul' },
    ],
    shots: [
      { team: 'home', min: 18, player: 'J. Álvarez', xg: 0.29, outcome: 'g', x: 86, y: 54 },
      { team: 'home', min: 74, player: 'Messi', xg: 0.24, outcome: 'g', x: 80, y: 42 },
      { team: 'home', min: 52, player: 'Di María', xg: 0.13, outcome: 's', x: 74, y: 60 },
      { team: 'home', min: 66, player: 'J. Álvarez', xg: 0.17, outcome: 'o', x: 82, y: 48 },
      { team: 'home', min: 88, player: 'L. Martínez', xg: 0.2, outcome: 's', x: 84, y: 52 },
      { team: 'away', min: 39, player: 'Duke', xg: 0.18, outcome: 'g', x: 84, y: 46 },
      { team: 'away', min: 57, player: 'Goodwin', xg: 0.1, outcome: 's', x: 76, y: 58 },
      { team: 'away', min: 70, player: 'McGree', xg: 0.06, outcome: 'o', x: 70, y: 38 },
    ],
  },
  {
    id: 'bra-ksa', home: 'BRA', away: 'KSA', score: [2, 0], ht: [1, 0], date: '21 Jun 2026', venue: 'SoFi Stadium', city: 'Los Angeles', ref: 'Slavko Vinčić', group: 'Group G',
    stats: { possession: [66, 34], xg: [2.4, 0.5], shots: [18, 5], sot: [7, 1], big: [4, 0], corners: [9, 1], fouls: [7, 13], yellow: [0, 2], red: [0, 0], passes: [668, 341], passAcc: [91, 80], tackles: [10, 19], saves: [1, 5] },
    timeline: [
      { min: 31, type: 'g', team: 'home', player: 'Vinícius Jr', assist: 'Raphinha' },
      { min: 49, type: 'y', team: 'away', player: 'Kanno' },
      { min: 66, type: 'g', team: 'home', player: 'Rodrygo', assist: 'Vinícius Jr' },
      { min: 73, type: 'y', team: 'away', player: 'Al-Amri' },
    ],
    shots: [
      { team: 'home', min: 31, player: 'Vinícius Jr', xg: 0.38, outcome: 'g', x: 88, y: 58 },
      { team: 'home', min: 66, player: 'Rodrygo', xg: 0.26, outcome: 'g', x: 84, y: 44 },
      { team: 'home', min: 22, player: 'Raphinha', xg: 0.14, outcome: 's', x: 76, y: 62 },
      { team: 'home', min: 54, player: 'Endrick', xg: 0.19, outcome: 'o', x: 82, y: 50 },
      { team: 'home', min: 79, player: 'Rodrygo', xg: 0.11, outcome: 'b', x: 72, y: 40 },
      { team: 'away', min: 40, player: 'Al-Dawsari', xg: 0.13, outcome: 's', x: 78, y: 52 },
      { team: 'away', min: 62, player: 'Al-Brikan', xg: 0.09, outcome: 'o', x: 74, y: 46 },
    ],
  },
  {
    id: 'ger-cro', home: 'GER', away: 'CRO', score: [3, 1], ht: [2, 0], date: '20 Jun 2026', venue: 'Lincoln Financial Field', city: 'Philadelphia', ref: 'Daniele Orsato', group: 'Group B',
    stats: { possession: [55, 45], xg: [2.7, 1.2], shots: [16, 10], sot: [7, 4], big: [4, 2], corners: [6, 5], fouls: [10, 11], yellow: [2, 2], red: [0, 0], passes: [548, 463], passAcc: [87, 84], tackles: [15, 16], saves: [3, 4] },
    timeline: [
      { min: 9, type: 'g', team: 'home', player: 'Musiala', assist: 'Wirtz' },
      { min: 44, type: 'g', team: 'home', player: 'Havertz', assist: 'Kimmich' },
      { min: 50, type: 'y', team: 'home', player: 'Andrich' },
      { min: 55, type: 'g', team: 'away', player: 'Budimir', assist: 'Modrić' },
      { min: 62, type: 'y', team: 'away', player: 'Brozović' },
      { min: 70, type: 'g', team: 'home', player: 'Wirtz', assist: 'Sané' },
      { min: 84, type: 'y', team: 'away', player: 'Sosa' },
    ],
    shots: [
      { team: 'home', min: 9, player: 'Musiala', xg: 0.2, outcome: 'g', x: 82, y: 60 },
      { team: 'home', min: 44, player: 'Havertz', xg: 0.44, outcome: 'g', x: 90, y: 48 },
      { team: 'home', min: 70, player: 'Wirtz', xg: 0.28, outcome: 'g', x: 84, y: 54 },
      { team: 'home', min: 33, player: 'Sané', xg: 0.12, outcome: 's', x: 74, y: 64 },
      { team: 'home', min: 77, player: 'Havertz', xg: 0.15, outcome: 'o', x: 80, y: 42 },
      { team: 'away', min: 55, player: 'Budimir', xg: 0.31, outcome: 'g', x: 86, y: 50 },
      { team: 'away', min: 67, player: 'Kramarić', xg: 0.16, outcome: 's', x: 78, y: 56 },
      { team: 'away', min: 38, player: 'Perišić', xg: 0.1, outcome: 'o', x: 72, y: 44 },
      { team: 'away', min: 81, player: 'Budimir', xg: 0.13, outcome: 'b', x: 76, y: 48 },
    ],
  },
  {
    id: 'eng-ecu', home: 'ENG', away: 'ECU', score: [1, 1], ht: [1, 0], date: '19 Jun 2026', venue: "Levi's Stadium", city: 'Santa Clara', ref: 'Facundo Tello', group: 'Group F',
    stats: { possession: [60, 40], xg: [1.6, 1.1], shots: [13, 9], sot: [4, 3], big: [2, 2], corners: [5, 4], fouls: [9, 12], yellow: [1, 2], red: [0, 0], passes: [589, 392], passAcc: [88, 82], tackles: [13, 17], saves: [2, 3] },
    timeline: [
      { min: 27, type: 'g', team: 'home', player: 'Kane', assist: 'Saka' },
      { min: 45, type: 'y', team: 'away', player: 'Caicedo' },
      { min: 61, type: 'g', team: 'away', player: 'E. Valencia', assist: 'Páez' },
      { min: 69, type: 'y', team: 'home', player: 'Rice' },
      { min: 78, type: 'y', team: 'away', player: 'Hincapié' },
    ],
    shots: [
      { team: 'home', min: 27, player: 'Kane', xg: 0.36, outcome: 'g', x: 88, y: 50 },
      { team: 'home', min: 54, player: 'Bellingham', xg: 0.13, outcome: 's', x: 76, y: 56 },
      { team: 'home', min: 72, player: 'Foden', xg: 0.11, outcome: 'o', x: 74, y: 44 },
      { team: 'home', min: 83, player: 'Watkins', xg: 0.18, outcome: 's', x: 82, y: 52 },
      { team: 'away', min: 61, player: 'E. Valencia', xg: 0.29, outcome: 'g', x: 86, y: 48 },
      { team: 'away', min: 48, player: 'Páez', xg: 0.12, outcome: 's', x: 76, y: 58 },
      { team: 'away', min: 75, player: 'Plata', xg: 0.08, outcome: 'o', x: 72, y: 40 },
    ],
  },
]
