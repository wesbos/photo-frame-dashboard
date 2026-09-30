// Mock data for the prototype. Everything is relative to "today" so the demo always looks current.
window.DATA = (function () {
  var base = new Date();
  base.setHours(0, 0, 0, 0);

  function at(d, hm) {
    var p = hm.split(':');
    var x = new Date(base);
    x.setDate(x.getDate() + d);
    x.setHours(+p[0], +p[1], 0, 0);
    return x;
  }
  var n = 0;
  function ev(d, s, e, title, people, extra) {
    return Object.assign({ id: 'e' + (++n), start: at(d, s), end: at(d, e), title: title, people: people }, extra || {});
  }
  function allDay(d, days, title, people, extra) {
    return Object.assign({ id: 'e' + (++n), allDay: true, start: at(d, '00:00'), end: at(d + days, '00:00'), title: title, people: people }, extra || {});
  }

  var ALL = ['alex', 'jordan', 'maya', 'otto'];

  var people = [
    { id: 'alex', name: 'Wes', color: '#2D5BFF', rgb: '45 91 255', ink: '#FFFFFF', home: false, status: 'Driving home', eta: 12 },
    { id: 'jordan', name: 'Claudia', color: '#E4007C', rgb: '228 0 124', ink: '#FFFFFF', home: false, status: 'At the office' },
    { id: 'maya', name: 'Buzzsaw', age: 10, color: '#00A36C', rgb: '0 163 108', ink: '#FFFFFF', home: true, status: 'Home' },
    { id: 'otto', name: 'Skidmark', age: 6, color: '#FFB000', rgb: '255 176 0', ink: '#111111', home: true, status: 'Home' }
  ];
  var family = { id: 'family', name: 'Family', color: '#111111', rgb: '17 17 17', ink: '#FFFFFF' };

  // ---------------------------------------------------------------- calendar
  var events = [
    // Today
    allDay(0, 1, 'Pajama Day at school', ['otto']),
    allDay(0, 1, 'Garbage + recycling night', ALL),
    ev(0, '07:00', '07:45', 'Gym', ['jordan'], { loc: 'Iron Works' }),
    ev(0, '08:15', '08:40', 'School drop-off', ['alex'], { travel: 10, loc: 'Parkdale Elementary' }),
    ev(0, '09:30', '10:30', 'Design review', ['jordan'], { loc: 'Office · Room 4B' }),
    ev(0, '12:00', '12:45', 'Dentist', ['maya', 'jordan'], { travel: 15, loc: 'Bright Smiles Dental' }),
    ev(0, '13:00', '14:00', 'Lunch with Sam', ['alex'], { loc: 'Café Rustica' }),
    ev(0, '15:45', '16:30', 'Piano lesson', ['otto'], { travel: 12, loc: "Ms. Park's Studio", notes: 'Bring the blue theory book.' }),
    ev(0, '16:05', '16:30', 'Drive Buzzsaw to soccer', ['jordan']),
    ev(0, '16:25', '16:50', 'Pick up Skidmark', ['jordan'], { loc: "Ms. Park's Studio" }),
    ev(0, '16:30', '18:00', 'Soccer practice', ['maya'], { travel: 20, loc: 'Lakeshore Fields', notes: 'Shin guards + water bottle. Rain likely — pack a jacket.' }),
    ev(0, '17:00', '17:30', 'Parent–teacher call', ['alex', 'jordan'], { loc: 'Zoom' }),
    ev(0, '18:30', '19:30', "Dinner at Nonna's", ALL, { travel: 20, loc: "Nonna's", notes: 'Bring the lemon cake.' }),
    ev(0, '20:00', '20:30', 'Bath + books', ['otto']),

    // Tomorrow → +6
    allDay(1, 3, 'Wes in Montréal', ['alex'], { loc: 'Hotel William Gray' }),
    ev(1, '07:00', '07:45', 'Gym', ['jordan'], { loc: 'Iron Works' }),
    ev(1, '08:15', '08:40', 'School drop-off', ['jordan'], { travel: 10 }),
    ev(1, '10:30', '11:15', 'Vet — Biscuit', ['jordan'], { travel: 10, loc: 'Riverdale Animal Clinic' }),
    ev(1, '15:30', '16:30', 'Art club', ['maya'], { loc: 'School' }),
    ev(1, '16:00', '18:00', 'Playdate with Leo', ['otto'], { travel: 8, loc: "Leo's house" }),
    ev(1, '19:00', '21:00', 'Book club', ['jordan'], { travel: 10, loc: "Priya's" }),

    ev(2, '09:00', '14:00', 'Science Centre trip', ['otto'], { loc: 'Ontario Science Centre' }),
    ev(2, '13:00', '13:45', 'Haircuts', ['maya', 'otto'], { travel: 10, loc: 'Snip Snip Kids' }),
    ev(2, '16:30', '18:00', 'Soccer practice', ['maya'], { travel: 20, loc: 'Lakeshore Fields' }),
    ev(2, '18:00', '19:30', 'Pizza night', ALL),

    ev(3, '10:00', '10:45', 'Swim lessons', ['otto'], { travel: 12, loc: 'Wellesley Pool' }),
    ev(3, '11:00', '12:00', 'Grocery run', ['jordan']),
    ev(3, '13:00', '15:30', "Zoe's birthday party", ['maya'], { travel: 15, loc: 'Pottery Place' }),
    ev(3, '19:00', '21:00', 'Movie night', ALL),

    ev(4, '10:30', '12:00', 'Sunday brunch', ALL, { travel: 15, loc: 'Lady Marmalade' }),
    ev(4, '17:05', '18:20', 'Flight home · AC 418', ['alex'], { loc: 'YUL → YYZ' }),

    ev(5, '07:00', '07:45', 'Gym', ['jordan']),
    ev(5, '15:45', '16:30', 'Piano lesson', ['otto'], { travel: 12 }),
    ev(5, '16:30', '18:00', 'Soccer practice', ['maya'], { travel: 20 }),
    ev(5, '19:00', '20:00', 'Yoga', ['jordan']),

    allDay(6, 2, 'Grandma visits', ALL),
    ev(6, '09:00', '09:45', 'Dentist', ['otto'], { travel: 15, loc: 'Bright Smiles Dental' }),
    ev(6, '16:30', '18:00', 'Soccer practice', ['maya'], { travel: 20 })
  ];

  // Background recurring events so the month view has texture
  for (var d = -40; d <= 45; d++) {
    if (d >= 0 && d <= 6) continue;
    var dow = new Date(at(d, '00:00')).getDay();
    if (dow === 1) events.push(ev(d, '15:45', '16:30', 'Piano lesson', ['otto']));
    if (dow === 2 || dow === 4) events.push(ev(d, '16:30', '18:00', 'Soccer practice', ['maya']));
    if (dow === 3) events.push(ev(d, '19:00', '20:00', 'Yoga', ['jordan']));
    if (dow === 6) events.push(ev(d, '10:00', '10:45', 'Swim lessons', ['otto']));
    if (dow === 0) events.push(ev(d, '17:30', '19:30', "Dinner at Nonna's", ALL));
    if (dow === 5 && d % 2 === 0) events.push(ev(d, '18:00', '19:30', 'Pizza night', ALL));
    if (d % 9 === 0) events.push(ev(d, '12:00', '13:00', 'Lunch meeting', ['alex']));
    if (d % 11 === 0) events.push(ev(d, '09:00', '10:00', 'Doctor', ['jordan']));
  }
  events.push(allDay(12, 1, "Buzzsaw's birthday 🎂", ALL));
  events.push(allDay(-8, 3, 'Cottage weekend', ALL));

  // Extra events for the "overloaded day" demo
  var busyExtras = [
    ev(0, '10:00', '11:00', 'Plumber window', ['jordan']),
    ev(0, '11:00', '11:30', 'Call with bank', ['alex']),
    ev(0, '14:30', '15:30', 'Library volunteer', ['jordan']),
    ev(0, '15:30', '16:00', 'Snack prep', ['maya']),
    ev(0, '16:00', '16:45', 'Math tutor', ['otto']),
    ev(0, '16:15', '17:00', 'Swim make-up', ['otto'], { travel: 10 }),
    ev(0, '19:45', '20:30', 'Bake sale prep', ['maya', 'jordan']),
    ev(0, '20:30', '21:30', 'Hockey', ['alex'], { travel: 15 })
  ];

  // ---------------------------------------------------------------- chores
  var routines = [
    { id: 'morning', name: 'Morning', range: '6 – 11 AM', from: 0, to: 11 },
    { id: 'after', name: 'After school', range: '11 AM – 5 PM', from: 11, to: 17 },
    { id: 'evening', name: 'Evening', range: '5 – 10 PM', from: 17, to: 24 }
  ];
  var cid = 0;
  function chore(r, who, title, emoji, stars, done, extra) {
    return Object.assign({ id: 'c' + (++cid), r: r, who: who, title: title, emoji: emoji, stars: stars, done: !!done }, extra || {});
  }
  var chores = [
    chore('morning', 'maya', 'Make bed', '🛏️', 1, true),
    chore('morning', 'maya', 'Brush teeth', '🪥', 1, true),
    chore('morning', 'maya', 'Pack backpack', '🎒', 1, true),
    chore('morning', 'otto', 'Make bed', '🛏️', 1, true),
    chore('morning', 'otto', 'Brush teeth', '🪥', 1, true),
    chore('morning', 'otto', 'Get dressed', '👕', 1, false),
    chore('morning', 'alex', 'School drop-off', '🚗', 0, true),
    chore('morning', 'jordan', 'Pack lunches', '🥪', 0, true),
    chore('morning', 'any', 'Feed Biscuit', '🐶', 1, true),

    chore('after', 'maya', 'Unpack lunchbox', '🥪', 1, true),
    chore('after', 'maya', 'Homework', '📚', 2, false),
    chore('after', 'maya', 'Pack soccer bag', '⚽', 1, false),
    chore('after', 'otto', 'Unpack lunchbox', '🥪', 1, true),
    chore('after', 'otto', 'Read for 20 min', '📖', 2, false),
    chore('after', 'otto', 'Practice piano', '🎹', 2, false),
    chore('after', 'otto', 'Tidy the Lego', '🧱', 1, false),
    chore('after', 'alex', 'Take out recycling', '♻️', 0, false, { overdue: true }),
    chore('after', 'alex', 'Call the plumber', '☎️', 0, true),
    chore('after', 'jordan', 'Fold laundry', '🧺', 0, false),
    chore('after', 'jordan', 'Order Zoe’s gift', '🎁', 0, true),
    chore('after', 'any', 'Water the plants', '🪴', 1, false),
    chore('after', 'any', 'Empty dishwasher', '🍽️', 2, false),
    chore('after', 'any', 'Walk Biscuit', '🐕', 2, true),

    chore('evening', 'maya', 'Set the table', '🍴', 1, false),
    chore('evening', 'maya', 'Lay out clothes', '👕', 1, false),
    chore('evening', 'maya', 'Shower', '🚿', 1, false),
    chore('evening', 'otto', 'Clear plates', '🍽️', 1, false),
    chore('evening', 'otto', 'Bath', '🛁', 1, false),
    chore('evening', 'otto', 'Lay out clothes', '👕', 1, false),
    chore('evening', 'alex', 'Lock up', '🔐', 0, false),
    chore('evening', 'jordan', 'Run dishwasher', '🫧', 0, false),
    chore('evening', 'any', 'Wipe counters', '🧽', 1, false),
    chore('evening', 'any', 'Garbage to curb', '🗑️', 2, false)
  ];
  var stars = { maya: 42, otto: 57 };
  // Mon..Sun, 1 = all chores done, 0 = missed, null = future
  var week = { maya: [1, 1, 0, 1, 1, 0, 1], otto: [1, 0, 1, 1, 1, 1, 0] };

  // ---------------------------------------------------------------- shopping
  var stores = [{ id: 'grocer', name: 'FreshCo' }, { id: 'costco', name: 'Costco' }];
  var catOrder = {
    all: ['Produce', 'Bakery', 'Meat & Fish', 'Dairy & Eggs', 'Pantry', 'Frozen', 'Snacks', 'Household'],
    grocer: ['Produce', 'Bakery', 'Meat & Fish', 'Dairy & Eggs', 'Pantry', 'Frozen', 'Snacks', 'Household'],
    costco: ['Household', 'Pantry', 'Snacks', 'Dairy & Eggs', 'Meat & Fish', 'Frozen', 'Produce', 'Bakery']
  };
  var gid = 0;
  function g(name, cat, qty, store, done, note) {
    return { id: 'g' + (++gid), name: name, cat: cat, qty: qty, store: store, done: !!done, note: note || '' };
  }
  var groceries = [
    g('Bananas', 'Produce', 1, 'grocer', false, 'Bunch, not too ripe'),
    g('Baby spinach', 'Produce', 1, 'grocer'),
    g('Avocados', 'Produce', 3, 'grocer'),
    g('Honeycrisp apples', 'Produce', 6, 'grocer'),
    g('Sourdough loaf', 'Bakery', 1, 'grocer'),
    g('Bagels', 'Bakery', 2, 'costco', false, 'Everything'),
    g('Chicken thighs', 'Meat & Fish', 1, 'grocer', false, 'Boneless'),
    g('Salmon fillets', 'Meat & Fish', 2, 'grocer'),
    g('Milk 2%', 'Dairy & Eggs', 2, 'costco'),
    g('Eggs', 'Dairy & Eggs', 1, 'costco', false, '2 dozen'),
    g('Greek yogurt', 'Dairy & Eggs', 1, 'grocer'),
    g('Aged cheddar', 'Dairy & Eggs', 1, 'grocer'),
    g('Rigatoni', 'Pantry', 2, 'grocer'),
    g('Olive oil', 'Pantry', 1, 'costco'),
    g('Coffee beans', 'Pantry', 1, 'grocer', false, 'Dark roast'),
    g('Frozen peas', 'Frozen', 1, 'grocer'),
    g('Waffles', 'Frozen', 1, 'grocer'),
    g('Goldfish crackers', 'Snacks', 1, 'costco'),
    g('Granola bars', 'Snacks', 1, 'grocer'),
    g('Paper towels', 'Household', 1, 'costco'),
    g('Dish soap', 'Household', 1, 'grocer'),
    g('Lemons', 'Produce', 2, 'grocer', true),
    g('Butter', 'Dairy & Eggs', 1, 'grocer', true),
    g('Tortillas', 'Bakery', 1, 'grocer', true)
  ];
  var catalog = [
    ['Apples', 'Produce'], ['Avocados', 'Produce'], ['Bananas', 'Produce'], ['Baby spinach', 'Produce'], ['Blueberries', 'Produce'],
    ['Broccoli', 'Produce'], ['Carrots', 'Produce'], ['Cucumber', 'Produce'], ['Garlic', 'Produce'], ['Grapes', 'Produce'],
    ['Lemons', 'Produce'], ['Limes', 'Produce'], ['Onions', 'Produce'], ['Potatoes', 'Produce'], ['Strawberries', 'Produce'],
    ['Tomatoes', 'Produce'], ['Bread', 'Bakery'], ['Bagels', 'Bakery'], ['Croissants', 'Bakery'], ['Sourdough loaf', 'Bakery'],
    ['Tortillas', 'Bakery'], ['Hamburger buns', 'Bakery'], ['Bacon', 'Meat & Fish'], ['Chicken breasts', 'Meat & Fish'],
    ['Chicken thighs', 'Meat & Fish'], ['Ground beef', 'Meat & Fish'], ['Salmon fillets', 'Meat & Fish'], ['Shrimp', 'Meat & Fish'],
    ['Butter', 'Dairy & Eggs'], ['Cheddar', 'Dairy & Eggs'], ['Cream cheese', 'Dairy & Eggs'], ['Eggs', 'Dairy & Eggs'],
    ['Greek yogurt', 'Dairy & Eggs'], ['Milk 2%', 'Dairy & Eggs'], ['Oat milk', 'Dairy & Eggs'], ['Parmesan', 'Dairy & Eggs'],
    ['Black beans', 'Pantry'], ['Cereal', 'Pantry'], ['Coffee beans', 'Pantry'], ['Flour', 'Pantry'], ['Honey', 'Pantry'],
    ['Maple syrup', 'Pantry'], ['Olive oil', 'Pantry'], ['Pasta sauce', 'Pantry'], ['Peanut butter', 'Pantry'], ['Rice', 'Pantry'],
    ['Rigatoni', 'Pantry'], ['Spaghetti', 'Pantry'], ['Sugar', 'Pantry'], ['Tea', 'Pantry'], ['Frozen peas', 'Frozen'],
    ['Frozen berries', 'Frozen'], ['Ice cream', 'Frozen'], ['Pizza', 'Frozen'], ['Waffles', 'Frozen'], ['Chips', 'Snacks'],
    ['Crackers', 'Snacks'], ['Dark chocolate', 'Snacks'], ['Goldfish crackers', 'Snacks'], ['Granola bars', 'Snacks'],
    ['Popcorn', 'Snacks'], ['Dish soap', 'Household'], ['Dishwasher pods', 'Household'], ['Garbage bags', 'Household'],
    ['Laundry detergent', 'Household'], ['Paper towels', 'Household'], ['Toilet paper', 'Household'], ['Toothpaste', 'Household']
  ];
  var usuals = ['Milk 2%', 'Eggs', 'Bananas', 'Bread', 'Apples', 'Coffee beans', 'Greek yogurt', 'Cheddar', 'Butter', 'Baby spinach', 'Chicken thighs', 'Paper towels'];

  // ---------------------------------------------------------------- home control
  var rooms = [
    { id: 'kitchen', name: 'Kitchen' },
    { id: 'living', name: 'Living Room' },
    { id: 'entry', name: 'Entry + Garage' },
    { id: 'upstairs', name: 'Upstairs' },
    { id: 'yard', name: 'Backyard' }
  ];
  var devices = [
    { id: 'k-pend', room: 'kitchen', type: 'light', name: 'Pendants', on: true, level: 80 },
    { id: 'k-under', room: 'kitchen', type: 'light', name: 'Under Cabinet', on: true, level: 55 },
    { id: 'k-island', room: 'kitchen', type: 'light', name: 'Island', on: false, level: 100 },
    { id: 'k-speaker', room: 'kitchen', type: 'blind', name: 'Window Shade', pos: 100 },
    { id: 'l-lamp', room: 'living', type: 'light', name: 'Floor Lamp', on: true, level: 45 },
    { id: 'l-ceil', room: 'living', type: 'light', name: 'Ceiling', on: false, level: 100 },
    { id: 'l-blinds', room: 'living', type: 'blind', name: 'Blinds', pos: 60 },
    { id: 'l-fire', room: 'living', type: 'light', name: 'Mantel', on: false, level: 70 },
    { id: 'e-door', room: 'entry', type: 'lock', name: 'Front Door', locked: true },
    { id: 'e-porch', room: 'entry', type: 'light', name: 'Porch', on: true, level: 100 },
    { id: 'g-door', room: 'entry', type: 'garage', name: 'Garage', state: 'closed' },
    { id: 'g-side', room: 'entry', type: 'lock', name: 'Side Door', locked: true },
    { id: 'u-maya', room: 'upstairs', type: 'light', name: "Buzzsaw's Lamp", on: true, level: 30 },
    { id: 'u-otto', room: 'upstairs', type: 'light', name: "Skidmark's Nightlight", on: false, level: 15 },
    { id: 'u-hall', room: 'upstairs', type: 'light', name: 'Hallway', on: false, level: 60 },
    { id: 'u-bath', room: 'upstairs', type: 'light', name: 'Bathroom', on: false, level: 100 },
    { id: 'y-string', room: 'yard', type: 'light', name: 'String Lights', on: false, level: 100, flaky: true },
    { id: 'y-back', room: 'yard', type: 'lock', name: 'Back Door', locked: true },
    { id: 'y-flood', room: 'yard', type: 'light', name: 'Floodlight', on: false, level: 100 }
  ];
  var climate = { current: 20.5, set: 21.5, mode: 'heat', humidity: 42, outside: 14 };
  var media = { room: 'Kitchen', title: 'Harvest Moon', artist: 'Neil Young', playing: true, volume: 35, seed: 'harvest-vinyl' };
  var cameras = [
    { id: 'c-front', name: 'Front Porch', seed: 'porch-steps' },
    { id: 'c-drive', name: 'Driveway', seed: 'driveway-maple' },
    { id: 'c-yard', name: 'Backyard', seed: 'garden-yard' }
  ];
  var scenes = [
    { id: 'morning', name: 'Morning', icon: 'sunrise', set: { 'k-pend': 100, 'k-under': 80, 'l-blinds': 100, 'l-lamp': 0, 'u-hall': 60 } },
    { id: 'dinner', name: 'Dinner', icon: 'utensils', set: { 'k-pend': 55, 'k-under': 30, 'k-island': 70, 'l-lamp': 40, 'l-ceil': 0 } },
    { id: 'movie', name: 'Movie', icon: 'film', set: { 'k-pend': 0, 'k-under': 15, 'k-island': 0, 'l-lamp': 15, 'l-ceil': 0, 'l-blinds': 0, 'l-fire': 30 } },
    { id: 'away', name: 'Away', icon: 'away', set: { 'k-pend': 0, 'k-under': 0, 'k-island': 0, 'l-lamp': 0, 'l-ceil': 0, 'l-fire': 0, 'u-maya': 0, 'u-hall': 0, 'e-porch': 100 } },
    { id: 'night', name: 'Goodnight', icon: 'moon', set: { 'k-pend': 0, 'k-under': 10, 'k-island': 0, 'l-lamp': 0, 'l-ceil': 0, 'l-fire': 0, 'u-hall': 10, 'u-otto': 15, 'e-porch': 0 } }
  ];

  // ---------------------------------------------------------------- weather (index = hour of day)
  var weather = {
    hi: 17, lo: 8, feels: -2, humidity: 71, wind: 18,
    t: [9, 9, 8, 8, 8, 8, 9, 10, 11, 12, 13, 15, 16, 17, 16, 15, 14, 13, 12, 12, 11, 10, 10, 9],
    c: ['moon', 'moon', 'moon', 'moon', 'moon', 'moon', 'partly', 'partly', 'sun', 'sun', 'sun', 'partly', 'partly', 'cloud', 'cloud', 'cloud', 'rain', 'rain', 'rain', 'rain', 'cloud', 'cloud', 'moon', 'moon'],
    p: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 5, 10, 20, 25, 40, 80, 90, 70, 55, 20, 10, 0, 0]
  };

  // ---------------------------------------------------------------- photos
  var t = new Date(base);
  var mmdd = ('0' + (t.getMonth() + 1)).slice(-2) + '-' + ('0' + t.getDate()).slice(-2);
  var photos = [
    { seed: 'tofino-surf', o: 'l', date: '2021-' + mmdd, place: 'Tofino, BC', from: 'jordan', tag: 'tofino' },
    { seed: 'cottage-dock', o: 'l', date: '2023-08-12', place: 'Lake of Bays', from: 'alex', tag: 'cottage' },
    { seed: 'maya-kite', o: 'p', date: '2024-05-19', place: 'Humber Bay Park', from: 'jordan', tag: 'spring24' },
    { seed: 'otto-kite', o: 'p', date: '2024-05-19', place: 'Humber Bay Park', from: 'alex', tag: 'spring24' },
    { seed: 'autumn-walk', o: 'l', date: '2022-10-09', place: 'High Park', from: 'alex', tag: 'fall22' },
    { seed: 'birthday-cake', o: 'p', date: '2025-10-12', place: 'Home', from: 'jordan', tag: 'bday25' },
    { seed: 'candles-lit', o: 'p', date: '2025-10-12', place: 'Home', from: 'alex', tag: 'bday25' },
    { seed: 'mountain-lake', o: 'l', date: '2019-' + mmdd, place: 'Banff, AB', from: 'alex', tag: 'banff' },
    { seed: 'snow-day', o: 'l', date: '2024-01-21', place: 'Riverdale Hill', from: 'jordan', tag: 'winter24' },
    { seed: 'beach-dunes', o: 'l', date: '2023-07-02', place: 'Sandbanks', from: 'maya', tag: 'sandbanks' },
    { seed: 'city-night', o: 'l', date: '2022-12-18', place: 'Nathan Phillips Sq.', from: 'jordan', tag: 'xmas22' },
    { seed: 'garden-bloom', o: 'p', date: '2025-06-08', place: 'Backyard', from: 'otto', tag: 'garden' },
    { seed: 'tomato-haul', o: 'p', date: '2025-06-08', place: 'Backyard', from: 'maya', tag: 'garden' },
    { seed: 'road-trip', o: 'l', date: '2024-08-04', place: 'Cabot Trail, NS', from: 'alex', tag: 'ns' },
    { seed: 'campfire', o: 'l', date: '2024-08-06', place: 'Cape Breton', from: 'jordan', tag: 'ns' },
    { seed: 'forest-path', o: 'l', date: '2020-09-26', place: 'Algonquin', from: 'alex', tag: 'algonquin' },
    { seed: 'pancakes', o: 'p', date: '2026-03-14', place: 'Home', from: 'maya', tag: 'pancakes' },
    { seed: 'sugar-shack', o: 'p', date: '2026-03-14', place: 'Sugar Shack', from: 'jordan', tag: 'pancakes' },
    { seed: 'harbour-sail', o: 'l', date: '2025-07-19', place: 'Toronto Harbour', from: 'otto', tag: 'sail' },
    { seed: 'pumpkins', o: 'l', date: '2025-10-25', place: "Chudleigh's", from: 'maya', tag: 'fall25' }
  ];

  return {
    people: people, family: family, ALL: ALL,
    events: events, busyExtras: busyExtras,
    routines: routines, chores: chores, stars: stars, week: week,
    stores: stores, catOrder: catOrder, groceries: groceries, catalog: catalog, usuals: usuals,
    rooms: rooms, devices: devices, climate: climate, media: media, cameras: cameras, scenes: scenes,
    weather: weather, photos: photos,
    _gid: function () { return 'g' + (++gid); },
    _eid: function () { return 'e' + (++n); }
  };
})();
