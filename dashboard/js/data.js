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

  var ALL = ['papa', 'maman', 'clara', 'felix'];

  var people = [
    { id: 'papa', name: 'Papa', color: '#2D5BFF', rgb: '45 91 255', ink: '#FFFFFF', home: false, status: 'En route', eta: 12 },
    { id: 'maman', name: 'Maman', color: '#E4007C', rgb: '228 0 124', ink: '#FFFFFF', home: false, status: 'Au bureau' },
    { id: 'clara', name: 'Clara', age: 6, color: '#00A36C', rgb: '0 163 108', ink: '#FFFFFF', home: true, status: 'À la maison' },
    { id: 'felix', name: 'Félix', age: 8, color: '#FFB000', rgb: '255 176 0', ink: '#111111', home: true, status: 'À la maison' }
  ];
  var family = { id: 'family', name: 'Famille', color: '#111111', rgb: '17 17 17', ink: '#FFFFFF' };

  // ---------------------------------------------------------------- calendar
  var events = [
    // Today
    allDay(0, 1, 'Pajama Day at school', ['felix']),
    ev(0, '07:00', '07:45', 'Gym', ['maman'], { loc: 'Iron Works' }),
    ev(0, '08:15', '08:40', 'School drop-off', ['papa'], { travel: 10, loc: 'Parkdale Elementary' }),
    ev(0, '09:30', '10:30', 'Design review', ['maman'], { loc: 'Office · Room 4B' }),
    ev(0, '12:00', '12:45', 'Dentist', ['clara', 'maman'], { travel: 15, loc: 'Bright Smiles Dental' }),
    ev(0, '13:00', '14:00', 'Lunch with Sam', ['papa'], { loc: 'Café Rustica' }),
    ev(0, '15:45', '16:30', 'Piano lesson', ['felix'], { travel: 12, loc: "Ms. Park's Studio", notes: 'Bring the blue theory book.' }),
    ev(0, '16:05', '16:30', 'Drive Clara to soccer', ['maman']),
    ev(0, '16:25', '16:50', 'Pick up Félix', ['maman'], { loc: "Ms. Park's Studio" }),
    ev(0, '16:30', '18:00', 'Soccer practice', ['clara'], { travel: 20, loc: 'Lakeshore Fields', notes: 'Shin guards + water bottle. Rain likely — pack a jacket.' }),
    ev(0, '17:00', '17:30', 'Parent–teacher call', ['papa', 'maman'], { loc: 'Zoom' }),
    ev(0, '18:30', '19:30', "Dinner at Nonna's", ALL, { travel: 20, loc: "Nonna's", notes: 'Bring the lemon cake.' }),
    ev(0, '20:00', '20:30', 'Bath + books', ['felix']),

    // Tomorrow → +6
    allDay(1, 3, 'Wes in Montréal', ['papa'], { loc: 'Hotel William Gray' }),
    ev(1, '07:00', '07:45', 'Gym', ['maman'], { loc: 'Iron Works' }),
    ev(1, '08:15', '08:40', 'School drop-off', ['maman'], { travel: 10 }),
    ev(1, '10:30', '11:15', 'Vet — Biscuit', ['maman'], { travel: 10, loc: 'Riverdale Animal Clinic' }),
    ev(1, '15:30', '16:30', 'Art club', ['clara'], { loc: 'School' }),
    ev(1, '16:00', '18:00', 'Playdate with Leo', ['felix'], { travel: 8, loc: "Leo's house" }),
    ev(1, '19:00', '21:00', 'Book club', ['maman'], { travel: 10, loc: "Priya's" }),

    ev(2, '09:00', '14:00', 'Science Centre trip', ['felix'], { loc: 'Ontario Science Centre' }),
    ev(2, '13:00', '13:45', 'Haircuts', ['clara', 'felix'], { travel: 10, loc: 'Snip Snip Kids' }),
    ev(2, '16:30', '18:00', 'Soccer practice', ['clara'], { travel: 20, loc: 'Lakeshore Fields' }),
    ev(2, '18:00', '19:30', 'Pizza night', ALL),

    ev(3, '10:00', '10:45', 'Swim lessons', ['felix'], { travel: 12, loc: 'Wellesley Pool' }),
    ev(3, '11:00', '12:00', 'Grocery run', ['maman']),
    ev(3, '13:00', '15:30', "Zoe's birthday party", ['clara'], { travel: 15, loc: 'Pottery Place' }),
    ev(3, '19:00', '21:00', 'Movie night', ALL),

    ev(4, '10:30', '12:00', 'Sunday brunch', ALL, { travel: 15, loc: 'Lady Marmalade' }),
    ev(4, '17:05', '18:20', 'Flight home · AC 418', ['papa'], { loc: 'YUL → YYZ' }),

    ev(5, '07:00', '07:45', 'Gym', ['maman']),
    ev(5, '15:45', '16:30', 'Piano lesson', ['felix'], { travel: 12 }),
    ev(5, '16:30', '18:00', 'Soccer practice', ['clara'], { travel: 20 }),
    ev(5, '19:00', '20:00', 'Yoga', ['maman']),

    allDay(6, 2, 'Grandma visits', ALL),
    ev(6, '09:00', '09:45', 'Dentist', ['felix'], { travel: 15, loc: 'Bright Smiles Dental' }),
    ev(6, '16:30', '18:00', 'Soccer practice', ['clara'], { travel: 20 })
  ];

  // Garbage/recycling: city alternates every Thursday. The Thursday of 2026-10-29 was a
  // garbage week, so weeks are counted from that fixed anchor (not from "today") so the
  // schedule stays correct no matter which day the app happens to load on.
  var GARBAGE_ANCHOR = new Date(2026, 9, 29); // Oct 29 2026 — a garbage Thursday
  function isGarbageWeek(thursday) {
    var weeks = Math.round((thursday - GARBAGE_ANCHOR) / (7 * 864e5));
    return ((weeks % 2) + 2) % 2 === 0;
  }

  // Garbage/recycling for the explicit "today → +6" window above. (Judo used to be a synthetic
  // placeholder here too, but it's now covered by the real imported calendar below — real data
  // always wins over a hand-authored placeholder for the same activity.)
  for (var dd = 0; dd <= 6; dd++) {
    var dowToday = new Date(at(dd, '00:00')).getDay();
    if (dowToday === 4) {
      var garbageToday = isGarbageWeek(at(dd, '00:00'));
      events.push(allDay(dd, 1, garbageToday ? 'Garbage night' : 'Recycling night', ALL, { bin: garbageToday ? 'garbage' : 'recycling' }));
    }
    if (dowToday === 3) {
      var garbageTomorrow = isGarbageWeek(at(dd + 1, '00:00'));
      events.push(allDay(dd, 1, garbageTomorrow ? 'Reminder: garbage tomorrow 🗑️' : 'Reminder: recycling tomorrow ♻️', ALL, { reminder: true }));
    }
  }

  // Background recurring events so the month view has texture
  for (var d = -40; d <= 45; d++) {
    if (d >= 0 && d <= 6) continue;
    var dow = new Date(at(d, '00:00')).getDay();
    if (dow === 1) events.push(ev(d, '15:45', '16:30', 'Piano lesson', ['felix']));
    if (dow === 3) events.push(ev(d, '19:00', '20:00', 'Yoga', ['maman']));
    if (dow === 6) events.push(ev(d, '10:00', '10:45', 'Swim lessons', ['felix']));
    if (dow === 0) events.push(ev(d, '17:30', '19:30', "Dinner at Nonna's", ALL));
    if (dow === 5 && d % 2 === 0) events.push(ev(d, '18:00', '19:30', 'Pizza night', ALL));
    if (d % 9 === 0) events.push(ev(d, '12:00', '13:00', 'Lunch meeting', ['papa']));
    if (d % 11 === 0) events.push(ev(d, '09:00', '10:00', 'Doctor', ['maman']));
    if (dow === 4) {
      var garbageWk = isGarbageWeek(at(d, '00:00'));
      events.push(allDay(d, 1, garbageWk ? 'Garbage night' : 'Recycling night', ALL, { bin: garbageWk ? 'garbage' : 'recycling' }));
    }
    if (dow === 3) {
      var garbageNextWk = isGarbageWeek(at(d + 1, '00:00'));
      events.push(allDay(d, 1, garbageNextWk ? 'Reminder: garbage tomorrow 🗑️' : 'Reminder: recycling tomorrow ♻️', ALL, { reminder: true }));
    }
  }
  events.push(allDay(-8, 3, 'Cottage weekend', ALL));

  // Real family calendar (imported from Google Calendar exports -- Lessards/Family/Birthdays
  // calendars, today forward). See scripts/ and dashboard/CLAUDE.md's "Pipelines" section for
  // how to re-run this import. Annual birthdays/anniversaries are deliberately only included
  // once (the nearest upcoming occurrence), not every year in the expansion window.
  var icalEvents = [];
  icalEvents.push(ev(0, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(1, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(2, 1, 'Frank off afternoon', ['papa']));
  icalEvents.push(ev(3, '09:00', '14:30', '2026 Rising Star Pre-Competitive Competition', ALL));
  icalEvents.push(ev(4, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(5, '18:45', '19:30', 'Tesla costco tire change', ALL, { loc: '300 RETAIL DRIVE' }));
  icalEvents.push(allDay(6, 1, 'Frank afternoon off', ['papa']));
  icalEvents.push(ev(6, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(7, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(8, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(10, '09:00', '10:00', 'GABBY @ mall', ALL));
  icalEvents.push(ev(10, '14:00', '16:00', 'Suzanne\'s Baby Shower', ALL, { loc: 'Oromocto Baptist Church' }));
  icalEvents.push(ev(11, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(13, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(14, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(15, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(16, 1, 'NO SCHOOL', ALL));
  icalEvents.push(allDay(16, 1, 'Frank off', ['papa']));
  icalEvents.push(ev(18, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(20, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(21, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(22, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(23, 1, 'Henry birthday 2019', ALL));
  icalEvents.push(allDay(24, 2, 'Christmas in the village st Martins', ALL));
  icalEvents.push(ev(24, '14:00', '16:30', 'Ticket: Frozen', ALL, { loc: 'Irving Oil Auditorium' }));
  icalEvents.push(ev(24, '16:00', '20:00', 'KV santa parade', ALL));
  icalEvents.push(ev(25, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(26, 5, 'Frank TO', ['papa']));
  icalEvents.push(ev(27, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(28, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(29, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(30, 3, 'Stay: Four Points by Sheraton Halifax', ALL, { loc: 'Four Points by Sheraton Halifax' }));
  icalEvents.push(allDay(30, 1, 'NO SCHOOL', ALL));
  icalEvents.push(allDay(31, 1, '2026 Winterfest Baton Twirling Championship', ALL));
  icalEvents.push(allDay(31, 1, 'PREP ST NICHOLAUS BOOT', ALL));
  icalEvents.push(allDay(32, 1, 'Cambridge supper', ALL));
  icalEvents.push(ev(32, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(34, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(35, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(36, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(39, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(41, '08:00', '08:30', 'Dry Cut Maintenance (Katrina Fraser', ALL, { loc: '154 Hampton Road, #103,Rothesay,New Brunswick,E2E2R3' }));
  icalEvents.push(ev(41, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(42, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(43, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(45, 1, 'Elkes Birthday', ALL));
  icalEvents.push(ev(46, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(47, 4, 'VACATION/NO SCHOOL', ALL));
  icalEvents.push(ev(47, '12:00', '13:00', 'Massage', ALL));
  icalEvents.push(allDay(48, 1, 'Frank off afternoon', ['papa']));
  icalEvents.push(ev(48, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(49, 2, 'Frank off', ['papa']));
  icalEvents.push(ev(49, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(50, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(53, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(54, 4, 'VACATION/NO SCHOOL', ALL));
  icalEvents.push(ev(55, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(56, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(allDay(57, 1, 'Frank afternoon off', ['papa']));
  icalEvents.push(ev(57, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(58, 1, 'New year\'s Day hike', ALL));
  icalEvents.push(ev(60, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(62, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(63, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(64, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(67, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(68, '12:00', '13:00', 'Clara East Coast Ped dentistry Moncton', ['clara']));
  icalEvents.push(ev(69, '14:00', '15:00', 'Dentist 🦷 Lisa', ALL));
  icalEvents.push(ev(69, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(70, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(71, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(74, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(75, '18:30', '19:30', 'Parent committee meeting', ALL));
  icalEvents.push(ev(76, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(77, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(78, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(79, 1, 'Jocelynes Bday', ALL));
  icalEvents.push(ev(81, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(83, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(84, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(85, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(86, 1, 'NO SCHOOL', ALL));
  icalEvents.push(allDay(87, 2, 'Kata clinic Fredericton', ALL));
  icalEvents.push(ev(88, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(90, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(91, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(92, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(95, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(97, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(98, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(99, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(100, 1, 'NO SCHOOL', ALL));
  icalEvents.push(allDay(100, 1, 'Lisa VAC', ALL));
  icalEvents.push(allDay(101, 3, 'Québec kayak w Latimer\'s', ALL));
  icalEvents.push(ev(102, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(103, 1, 'Lisa VAC', ALL));
  icalEvents.push(allDay(103, 1, 'Kyle Latimer\'s birthday', ALL));
  icalEvents.push(ev(104, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(105, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(106, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(108, '09:00', '10:00', 'Clara bday party?', ['clara']));
  icalEvents.push(ev(109, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(110, 1, 'Claras birthday', ['clara']));
  icalEvents.push(ev(111, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(112, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(113, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(116, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(117, 5, 'MARCH BREAK VACATION', ALL));
  icalEvents.push(ev(118, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(119, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(120, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(123, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(125, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(126, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(127, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(129, 1, 'Viktoria Stührenberg 2025', ALL));
  icalEvents.push(ev(130, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(132, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(133, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(allDay(134, 1, 'Lisa\'s bday', ALL));
  icalEvents.push(ev(134, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(135, 1, 'NO SCHOOL', ALL));
  icalEvents.push(allDay(136, 2, 'NB OPEN ROTHESAY', ALL));
  icalEvents.push(allDay(137, 1, 'Rothesay youth Open', ALL));
  icalEvents.push(ev(137, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(139, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(140, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(141, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(142, '09:00', '10:00', 'Good Fri, NO SCHOOL, OFF', ALL));
  icalEvents.push(ev(144, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(145, '09:00', '10:00', 'EASTER, No SCHOOL, Lisa OFF', ALL));
  icalEvents.push(allDay(146, 1, 'André 1987', ALL));
  icalEvents.push(ev(146, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(147, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(148, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(149, 1, 'NO SCHOOL', ALL));
  icalEvents.push(allDay(149, 1, 'Megan Latimer\'s birthday', ALL));
  icalEvents.push(ev(151, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(153, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(154, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(allDay(155, 3, 'Grapevine', ALL));
  icalEvents.push(ev(155, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(158, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(160, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(161, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(162, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(163, 1, 'NO SCHOOL', ALL));
  icalEvents.push(ev(164, '10:00', '11:00', 'Plan Maibaum?', ALL));
  icalEvents.push(allDay(165, 1, 'Leona Armstrong birthday', ALL));
  icalEvents.push(ev(165, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(167, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(168, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(169, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(172, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(173, '15:00', '16:00', 'Clara and Felix dentist 🦷', ['felix', 'clara']));
  icalEvents.push(ev(174, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(175, 1, 'Suzanne birthday 1992', ALL));
  icalEvents.push(ev(175, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(176, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(179, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(181, 1, 'Emil Birthday 2017', ALL));
  icalEvents.push(ev(181, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(182, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(183, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(184, 1, 'NO SCHOOL', ALL));
  icalEvents.push(ev(186, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(188, 1, 'Léo Lessard birthday 2020', ALL));
  icalEvents.push(ev(188, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(189, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(190, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(193, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(195, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(196, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(197, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(198, 1, 'NO SCHOOL', ALL));
  icalEvents.push(allDay(198, 1, 'Cynthia Birthday', ALL));
  icalEvents.push(allDay(199, 1, 'Will & kat anniversary', ALL));
  icalEvents.push(ev(200, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(202, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(203, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(204, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(207, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(209, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(210, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(211, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(214, 1, 'Cedric birthday 2018', ALL));
  icalEvents.push(ev(214, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(allDay(215, 1, 'Ariel birthday', ALL));
  icalEvents.push(ev(216, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(217, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(218, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(220, 1, 'Kris zanatta birthday', ALL));
  icalEvents.push(allDay(220, 1, 'Emerson Theodore Chase birthday 2019', ALL));
  icalEvents.push(ev(221, '10:00', '11:00', 'Kinder Judo', ALL));
  icalEvents.push(ev(223, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(ev(224, '18:00', '19:00', 'Baton', ALL));
  icalEvents.push(ev(225, '18:00', '19:00', 'Judo', ALL));
  icalEvents.push(allDay(226, 1, 'NO SCHOOL', ALL));
  icalEvents.push(allDay(233, 1, 'LAST DAY OF SCHOOL', ALL));
  icalEvents.push(allDay(233, 1, 'F&L dating Anniversary 2011', ALL));
  icalEvents.push(allDay(237, 1, 'Noah Journeay 2020', ALL));
  icalEvents.push(allDay(250, 1, 'William pollabauer 2020', ALL));
  icalEvents.push(allDay(262, 1, 'Suzanne Kyle 2021', ALL));
  icalEvents.push(allDay(265, 1, 'Chantal 1984', ALL));
  icalEvents.push(allDay(271, 1, 'Adolf\'s birthday', ALL));
  icalEvents.push(allDay(272, 1, 'Thea Zanatta 2022', ALL));
  icalEvents.push(ev(281, '11:00', '12:00', 'Twin shores WE 120', ALL));
  icalEvents.push(allDay(288, 1, 'Our wedding Anniversary 2017', ALL));
  icalEvents.push(allDay(290, 1, 'Kyle\'s birthday', ALL));
  icalEvents.push(allDay(295, 1, 'tina\'s birthday', ALL));
  icalEvents.push(allDay(295, 4, 'party PaPa', ['papa']));
  icalEvents.push(allDay(311, 1, 'Dan birthday 1957', ALL));
  icalEvents.push(allDay(317, 1, 'Johannas Birthday', ALL));
  icalEvents.push(allDay(322, 1, 'TinaKris Zanatta anniversary 2018', ALL));
  icalEvents.push(allDay(324, 1, 'Ethan pollabauer 2018', ALL));
  icalEvents.push(allDay(326, 1, 'dan & joc Lessard anniversary', ALL));
  icalEvents.push(allDay(326, 1, 'Journeay anniversary 2015', ALL));
  icalEvents.push(ev(328, '09:00', '10:00', 'Orange shirt day reminder', ALL));
  icalEvents.push(allDay(337, 1, 'Alec birthday 2020', ALL));
  icalEvents.push(allDay(339, 1, 'FRANKS BDAY 1985', ALL));
  icalEvents.push(allDay(352, 1, 'Félix’s birthday 2018', ['felix']));
  icalEvents.push(allDay(396, 1, 'PREP ST NICHOLAUS BOOT', ALL));
  icalEvents.push(allDay(423, 1, 'New year\'s Day hike', ALL));
  icalEvents.push(allDay(495, 1, 'Viktoria Stührenberg 2025', ALL));
  icalEvents.push(allDay(512, 1, 'André 1987', ALL));
  icalEvents.push(ev(530, '10:00', '11:00', 'Plan Maibaum?', ALL));
  icalEvents.push(allDay(603, 1, 'Noah Journeay 2020', ALL));
  icalEvents.push(allDay(616, 1, 'William pollabauer 2020', ALL));
  icalEvents.push(allDay(628, 1, 'Suzanne Kyle 2021', ALL));
  icalEvents.push(allDay(631, 1, 'Chantal 1984', ALL));
  icalEvents.push(allDay(638, 1, 'Thea Zanatta 2022', ALL));
  icalEvents.push(ev(674, '11:00', '12:00', 'Lasik appt', ALL));
  icalEvents.push(allDay(690, 1, 'Ethan pollabauer 2018', ALL));
  icalEvents.push(ev(694, '09:00', '10:00', 'Orange shirt day reminder', ALL));
  // From the Family and Birthdays Google Calendar exports (narrower follow-up import — only
  // birthdays/holidays/no-school days were brought in from those, everything else was either
  // off-topic personal/work noise or already covered by the Lessards calendar above).
  icalEvents.push(allDay(241, 1, 'Christian Lessard birthday', ALL));
  icalEvents.push(allDay(339, 1, "Papa's birthday 🎂", ['papa']));
  events = events.concat(icalEvents);


  // Extra events for the "overloaded day" demo
  var busyExtras = [
    ev(0, '10:00', '11:00', 'Plumber window', ['maman']),
    ev(0, '11:00', '11:30', 'Call with bank', ['papa']),
    ev(0, '14:30', '15:30', 'Library volunteer', ['maman']),
    ev(0, '15:30', '16:00', 'Snack prep', ['clara']),
    ev(0, '16:00', '16:45', 'Math tutor', ['felix']),
    ev(0, '16:15', '17:00', 'Swim make-up', ['felix'], { travel: 10 }),
    ev(0, '19:45', '20:30', 'Bake sale prep', ['clara', 'maman']),
    ev(0, '20:30', '21:30', 'Hockey', ['papa'], { travel: 15 })
  ];

  // ---------------------------------------------------------------- chores
  var routines = [
    { id: 'morning', name: 'Matin', range: '6 h – 11 h', from: 0, to: 11 },
    { id: 'after', name: 'Après l’école', range: '11 h – 17 h', from: 11, to: 17 },
    { id: 'evening', name: 'Soir', range: '17 h – 22 h', from: 17, to: 24 }
  ];
  var cid = 0;
  function chore(r, who, title, emoji, stars, done, extra) {
    return Object.assign({ id: 'c' + (++cid), r: r, who: who, title: title, emoji: emoji, stars: stars, done: !!done }, extra || {});
  }
  var chores = [
    chore('morning', 'clara', 'Make bed', '🛏️', 1, true),
    chore('morning', 'clara', 'Brush teeth', '🪥', 1, true),
    chore('morning', 'clara', 'Pack backpack', '🎒', 1, true),
    chore('morning', 'felix', 'Make bed', '🛏️', 1, true),
    chore('morning', 'felix', 'Brush teeth', '🪥', 1, true),
    chore('morning', 'felix', 'Get dressed', '👕', 1, false),
    chore('morning', 'papa', 'School drop-off', '🚗', 0, true),
    chore('morning', 'maman', 'Pack lunches', '🥪', 0, true),
    chore('morning', 'any', 'Feed Biscuit', '🐶', 1, true),

    chore('after', 'clara', 'Unpack lunchbox', '🥪', 1, true),
    chore('after', 'clara', 'Homework', '📚', 2, false),
    chore('after', 'clara', 'Pack soccer bag', '⚽', 1, false),
    chore('after', 'felix', 'Unpack lunchbox', '🥪', 1, true),
    chore('after', 'felix', 'Read for 20 min', '📖', 2, false),
    chore('after', 'felix', 'Practice piano', '🎹', 2, false),
    chore('after', 'felix', 'Tidy the Lego', '🧱', 1, false),
    chore('after', 'papa', 'Take out recycling', '♻️', 0, false, { overdue: true }),
    chore('after', 'papa', 'Call the plumber', '☎️', 0, true),
    chore('after', 'maman', 'Fold laundry', '🧺', 0, false),
    chore('after', 'maman', 'Order Zoe’s gift', '🎁', 0, true),
    chore('after', 'any', 'Water the plants', '🪴', 1, false),
    chore('after', 'any', 'Empty dishwasher', '🍽️', 2, false),
    chore('after', 'any', 'Walk Biscuit', '🐕', 2, true),

    chore('evening', 'clara', 'Set the table', '🍴', 1, false),
    chore('evening', 'clara', 'Lay out clothes', '👕', 1, false),
    chore('evening', 'clara', 'Shower', '🚿', 1, false),
    chore('evening', 'felix', 'Clear plates', '🍽️', 1, false),
    chore('evening', 'felix', 'Bath', '🛁', 1, false),
    chore('evening', 'felix', 'Lay out clothes', '👕', 1, false),
    chore('evening', 'papa', 'Lock up', '🔐', 0, false),
    chore('evening', 'maman', 'Run dishwasher', '🫧', 0, false),
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
    { seed: 'tofino-surf', o: 'l', date: '2021-' + mmdd, place: 'Tofino, BC', from: 'maman', tag: 'tofino' },
    { seed: 'cottage-dock', o: 'l', date: '2023-08-12', place: 'Lake of Bays', from: 'papa', tag: 'cottage' },
    { seed: 'maya-kite', o: 'p', date: '2024-05-19', place: 'Humber Bay Park', from: 'maman', tag: 'spring24' },
    { seed: 'otto-kite', o: 'p', date: '2024-05-19', place: 'Humber Bay Park', from: 'papa', tag: 'spring24' },
    { seed: 'autumn-walk', o: 'l', date: '2022-10-09', place: 'High Park', from: 'papa', tag: 'fall22' },
    { seed: 'birthday-cake', o: 'p', date: '2025-10-12', place: 'Home', from: 'maman', tag: 'bday25' },
    { seed: 'candles-lit', o: 'p', date: '2025-10-12', place: 'Home', from: 'papa', tag: 'bday25' },
    { seed: 'mountain-lake', o: 'l', date: '2019-' + mmdd, place: 'Banff, AB', from: 'papa', tag: 'banff' },
    { seed: 'snow-day', o: 'l', date: '2024-01-21', place: 'Riverdale Hill', from: 'maman', tag: 'winter24' },
    { seed: 'beach-dunes', o: 'l', date: '2023-07-02', place: 'Sandbanks', from: 'clara', tag: 'sandbanks' },
    { seed: 'city-night', o: 'l', date: '2022-12-18', place: 'Nathan Phillips Sq.', from: 'maman', tag: 'xmas22' },
    { seed: 'garden-bloom', o: 'p', date: '2025-06-08', place: 'Backyard', from: 'felix', tag: 'garden' },
    { seed: 'tomato-haul', o: 'p', date: '2025-06-08', place: 'Backyard', from: 'clara', tag: 'garden' },
    { seed: 'road-trip', o: 'l', date: '2024-08-04', place: 'Cabot Trail, NS', from: 'papa', tag: 'ns' },
    { seed: 'campfire', o: 'l', date: '2024-08-06', place: 'Cape Breton', from: 'maman', tag: 'ns' },
    { seed: 'forest-path', o: 'l', date: '2020-09-26', place: 'Algonquin', from: 'papa', tag: 'algonquin' },
    { seed: 'pancakes', o: 'p', date: '2026-03-14', place: 'Home', from: 'clara', tag: 'pancakes' },
    { seed: 'sugar-shack', o: 'p', date: '2026-03-14', place: 'Sugar Shack', from: 'maman', tag: 'pancakes' },
    { seed: 'harbour-sail', o: 'l', date: '2025-07-19', place: 'Toronto Harbour', from: 'felix', tag: 'sail' },
    { seed: 'pumpkins', o: 'l', date: '2025-10-25', place: "Chudleigh's", from: 'clara', tag: 'fall25' }
  ];

  // ---------------------------------------------------------------- AI agent usage (CodexBar-style)
  // left = minutes until the window resets; win = window length in minutes (for pace)
  var H5 = 300, DAY = 1440, WEEK = 10080, MONTH = 43200;
  var agents = [
    {
      id: 'claude', name: 'Claude', plan: 'Max 20×', color: '#D97757', rgb: '217 119 87', status: 'ok',
      meters: [
        { label: 'Session', win: H5, used: 62, left: 134 },
        { label: 'Weekly · all models', win: WEEK, used: 41, left: 4680 }
      ],
      tokens: 3.1, cost: 21.4, week: [2.2, 3.8, 2.9, 4.4, 1.6, 0.8, 3.1]
    },
    {
      id: 'codex', name: 'Codex', plan: 'ChatGPT Pro', color: '#10A37F', rgb: '16 163 127', status: 'ok',
      meters: [
        { label: 'Session', win: H5, used: 88, left: 38 },
        { label: 'Weekly', win: WEEK, used: 57, left: 7320 }
      ],
      tokens: 4.6, cost: 17.9, week: [3.1, 2.4, 5.2, 4.0, 2.2, 1.1, 4.6]
    },
    {
      id: 'cursor', name: 'Cursor', plan: 'Pro+', color: '#111111', rgb: '17 17 17', status: 'ok',
      meters: [
        { label: 'Included usage', win: MONTH, used: 76, left: 17280, detail: '$45.60 of $60' },
        { label: 'On-demand', win: MONTH, used: 16, left: 17280, detail: '$8.20 of $50 cap' }
      ],
      tokens: 1.8, cost: 6.3, week: [1.2, 1.9, 0.7, 2.3, 1.5, 0.4, 1.8]
    },
    {
      id: 'gemini', name: 'Gemini', plan: 'AI Ultra', color: '#3F6FE4', rgb: '63 111 228', status: 'ok',
      meters: [
        { label: 'Requests · daily', win: DAY, used: 16, left: 522, detail: '320 of 2,000' },
        { label: 'Pro model · daily', win: DAY, used: 52, left: 522, detail: '104 of 200' }
      ],
      tokens: 0.9, cost: 0, week: [0.4, 1.1, 0.6, 0.2, 0.9, 1.3, 0.9]
    },
    {
      id: 'copilot', name: 'Copilot', plan: 'Pro+', color: '#8957E5', rgb: '137 87 229', status: 'degraded', incident: 'Elevated errors on coding agent',
      meters: [
        { label: 'Premium requests', win: MONTH, used: 75, left: 17280, detail: '1,124 of 1,500' },
        { label: 'Coding agent', win: MONTH, used: 38, left: 17280, detail: '19 of 50 sessions' }
      ],
      tokens: 1.2, cost: 0, week: [0.9, 1.4, 1.1, 0.8, 1.6, 0.3, 1.2]
    }
  ];

  return {
    people: people, family: family, ALL: ALL,
    events: events, busyExtras: busyExtras,
    routines: routines, chores: chores, stars: stars, week: week,
    stores: stores, catOrder: catOrder, groceries: groceries, catalog: catalog, usuals: usuals,
    rooms: rooms, devices: devices, climate: climate, media: media, cameras: cameras, scenes: scenes,
    weather: weather, photos: photos, agents: agents,
    _gid: function () { return 'g' + (++gid); },
    _eid: function () { return 'e' + (++n); }
  };
})();
