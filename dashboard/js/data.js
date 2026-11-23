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

  var ALL = ['paxton', 'anders', 'tucker'];

  var people = [
    { id: 'paxton', name: 'Paxton', age: 16, color: '#2D5BFF', rgb: '45 91 255', ink: '#FFFFFF', home: true, status: 'Home' },
    { id: 'anders', name: 'Anders', age: 14, color: '#00A36C', rgb: '0 163 108', ink: '#FFFFFF', home: true, status: 'Home' },
    { id: 'tucker', name: 'Tucker', age: 10, color: '#FFB000', rgb: '255 176 0', ink: '#111111', home: true, status: 'Home' }
  ];
  var family = { id: 'family', name: 'Family', color: '#111111', rgb: '17 17 17', ink: '#FFFFFF' };

  // ---------------------------------------------------------------- calendar
  var events = [];

  // Extra events for the "overloaded day" demo
  var busyExtras = [];

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
    chore('morning', 'paxton', 'Make bed', '🛏️', 1, true),
    chore('morning', 'paxton', 'Brush teeth', '🪥', 1, true),
    chore('morning', 'anders', 'Make bed', '🛏️', 1, true),
    chore('morning', 'anders', 'Brush teeth', '🪥', 1, true),
    chore('morning', 'anders', 'Pack backpack', '🎒', 1, false),
    chore('morning', 'tucker', 'Make bed', '🛏️', 1, true),
    chore('morning', 'tucker', 'Brush teeth', '🪥', 1, true),
    chore('morning', 'tucker', 'Get dressed', '👕', 1, false),
    chore('morning', 'any', 'Empty dishwasher', '🍽️', 2, true),

    chore('after', 'paxton', 'Homework', '📚', 2, false),
    chore('after', 'paxton', 'Take out trash', '🗑️', 1, false),
    chore('after', 'anders', 'Homework', '📚', 2, false),
    chore('after', 'anders', 'Practice', '🎵', 1, false),
    chore('after', 'tucker', 'Homework', '📚', 2, false),
    chore('after', 'tucker', 'Read for 20 min', '📖', 2, false),
    chore('after', 'any', 'Water the plants', '🪴', 1, false),
    chore('after', 'any', 'Bring in the mail', '📬', 1, true),

    chore('evening', 'paxton', 'Set the table', '🍴', 1, false),
    chore('evening', 'paxton', 'Shower', '🚿', 1, false),
    chore('evening', 'anders', 'Clear plates', '🍽️', 1, false),
    chore('evening', 'anders', 'Shower', '🚿', 1, false),
    chore('evening', 'tucker', 'Clear plates', '🍽️', 1, false),
    chore('evening', 'tucker', 'Lay out clothes', '👕', 1, false),
    chore('evening', 'any', 'Wipe counters', '🧽', 1, false),
    chore('evening', 'any', 'Lock up', '🔐', 1, false)
  ];
  var stars = { paxton: 38, anders: 45, tucker: 52 };
  // Mon..Sun, 1 = all chores done, 0 = missed, null = future
  var week = { paxton: [1, 0, 1, 1, 1, 0, 1], anders: [1, 1, 0, 1, 1, 1, 0], tucker: [1, 0, 1, 1, 1, 1, 0] };

  // ---------------------------------------------------------------- shopping
  var stores = [{ id: 'kroger', name: 'Kroger' }, { id: 'publix', name: 'Publix' }];
  var catOrder = {
    all: ['Produce', 'Bakery', 'Meat & Fish', 'Dairy & Eggs', 'Pantry', 'Frozen', 'Snacks', 'Household'],
    kroger: ['Produce', 'Bakery', 'Meat & Fish', 'Dairy & Eggs', 'Pantry', 'Frozen', 'Snacks', 'Household'],
    publix: ['Produce', 'Bakery', 'Dairy & Eggs', 'Meat & Fish', 'Pantry', 'Frozen', 'Snacks', 'Household']
  };
  var gid = 0;
  function g(name, cat, qty, store, done, note) {
    return { id: 'g' + (++gid), name: name, cat: cat, qty: qty, store: store, done: !!done, note: note || '' };
  }
  var groceries = [
    g('Bananas', 'Produce', 1, 'kroger', false, 'Bunch, not too ripe'),
    g('Baby spinach', 'Produce', 1, 'kroger'),
    g('Avocados', 'Produce', 3, 'publix'),
    g('Honeycrisp apples', 'Produce', 6, 'kroger'),
    g('Sourdough loaf', 'Bakery', 1, 'publix'),
    g('Bagels', 'Bakery', 2, 'kroger', false, 'Everything'),
    g('Chicken thighs', 'Meat & Fish', 1, 'publix', false, 'Boneless'),
    g('Salmon fillets', 'Meat & Fish', 2, 'publix'),
    g('Milk 2%', 'Dairy & Eggs', 2, 'kroger'),
    g('Eggs', 'Dairy & Eggs', 1, 'kroger', false, '2 dozen'),
    g('Greek yogurt', 'Dairy & Eggs', 1, 'publix'),
    g('Shredded cheddar', 'Dairy & Eggs', 1, 'kroger'),
    g('Rigatoni', 'Pantry', 2, 'kroger'),
    g('Olive oil', 'Pantry', 1, 'publix'),
    g('Coffee beans', 'Pantry', 1, 'kroger', false, 'Dark roast'),
    g('Frozen peas', 'Frozen', 1, 'kroger'),
    g('Waffles', 'Frozen', 1, 'kroger'),
    g('Goldfish crackers', 'Snacks', 1, 'kroger'),
    g('Granola bars', 'Snacks', 1, 'publix'),
    g('Paper towels', 'Household', 1, 'kroger'),
    g('Dish soap', 'Household', 1, 'publix'),
    g('Lemons', 'Produce', 2, 'kroger', true),
    g('Butter', 'Dairy & Eggs', 1, 'publix', true),
    g('Tortillas', 'Bakery', 1, 'kroger', true)
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
    { seed: 'tofino-surf', o: 'l', date: '2021-' + mmdd, place: 'Kentucky River', from: 'paxton', tag: 'river' },
    { seed: 'cottage-dock', o: 'l', date: '2023-08-12', place: 'Lake Cumberland', from: 'anders', tag: 'lake' },
    { seed: 'maya-kite', o: 'p', date: '2024-05-19', place: 'Versailles, KY', from: 'tucker', tag: 'spring24' },
    { seed: 'otto-kite', o: 'p', date: '2024-05-19', place: 'Versailles, KY', from: 'paxton', tag: 'spring24' },
    { seed: 'autumn-walk', o: 'l', date: '2022-10-09', place: 'Keeneland', from: 'anders', tag: 'fall22' },
    { seed: 'birthday-cake', o: 'p', date: '2025-10-12', place: 'Home', from: 'tucker', tag: 'bday25' },
    { seed: 'candles-lit', o: 'p', date: '2025-10-12', place: 'Home', from: 'paxton', tag: 'bday25' },
    { seed: 'mountain-lake', o: 'l', date: '2019-' + mmdd, place: 'Red River Gorge', from: 'anders', tag: 'gorge' },
    { seed: 'snow-day', o: 'l', date: '2024-01-21', place: 'Versailles, KY', from: 'tucker', tag: 'winter24' },
    { seed: 'beach-dunes', o: 'l', date: '2023-07-02', place: 'Myrtle Beach', from: 'paxton', tag: 'beach' },
    { seed: 'city-night', o: 'l', date: '2022-12-18', place: 'Lexington, KY', from: 'anders', tag: 'xmas22' },
    { seed: 'garden-bloom', o: 'p', date: '2025-06-08', place: 'Backyard', from: 'tucker', tag: 'garden' },
    { seed: 'tomato-haul', o: 'p', date: '2025-06-08', place: 'Backyard', from: 'paxton', tag: 'garden' },
    { seed: 'road-trip', o: 'l', date: '2024-08-04', place: 'Smoky Mountains', from: 'anders', tag: 'smokies' },
    { seed: 'campfire', o: 'l', date: '2024-08-06', place: 'Daniel Boone Forest', from: 'paxton', tag: 'camping' },
    { seed: 'forest-path', o: 'l', date: '2020-09-26', place: 'Natural Bridge', from: 'tucker', tag: 'hiking' },
    { seed: 'pancakes', o: 'p', date: '2026-03-14', place: 'Home', from: 'anders', tag: 'breakfast' },
    { seed: 'sugar-shack', o: 'p', date: '2026-03-14', place: 'Woodford Reserve', from: 'paxton', tag: 'bourbon' },
    { seed: 'harbour-sail', o: 'l', date: '2025-07-19', place: 'Lake Cumberland', from: 'tucker', tag: 'lake' },
    { seed: 'pumpkins', o: 'l', date: '2025-10-25', place: 'Evans Orchard', from: 'anders', tag: 'fall25' }
  ];

  return {
    people: people, family: family, ALL: ALL,
    events: events, busyExtras: busyExtras,
    routines: routines, chores: chores, stars: stars, week: week,
    stores: stores, catOrder: catOrder, groceries: groceries, catalog: catalog, usuals: usuals,
    weather: weather, photos: photos,
    _gid: function () { return 'g' + (++gid); },
    _eid: function () { return 'e' + (++n); }
  };
})();
