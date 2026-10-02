(function () {
  var cfg = window.ATTENDANCE_CONFIG;
  var state = {
    records: Object.assign({}, cfg.initialRecords),
    viewYear: cfg.currentYear,
    viewMonth: cfg.currentMonth
  };

  var STATUS = {
    WFH: { label: 'Work From Home', color: '#2563EB' },
    WFO: { label: 'Work From Office', color: '#16A34A' },
    Leave: { label: 'Leave', color: '#D97706' },
    Holiday: { label: 'Holiday', color: '#7C3AED' }
  };
  var STATUS_ORDER = ['WFH', 'WFO', 'Leave', 'Holiday'];
  var MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  var root = document.getElementById('app-root');
  var today = new Date();
  var todayKey = dateKey(today.getFullYear(), today.getMonth(), today.getDate());

  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function dateKey(y, m, d) { return y + '-' + pad(m + 1) + '-' + pad(d); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function saveStatus(key, status) {
    var body = new URLSearchParams();
    body.set('date', key);
    body.set('status', status || '');
    return fetch(cfg.setStatusUrl, {
      method: 'POST',
      headers: {
        'X-CSRFToken': cfg.csrfToken,
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: body.toString(),
      credentials: 'same-origin'
    }).then(function (resp) {
      if (!resp.ok) throw new Error('save failed');
      return resp.json();
    });
  }

  function closeModal() {
    var ov = document.querySelector('.modal-overlay');
    if (ov) ov.remove();
  }

  function openModal(y, m, d) {
    closeModal();
    var key = dateKey(y, m, d);
    var current = state.records[key];
    var dateObj = new Date(y, m, d);
    var overlay = el('div', 'modal-overlay');
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeModal(); });
    var box = el('div', 'modal-box');
    box.appendChild(el('h2', null, dateObj.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })));
    box.appendChild(el('p', 'sub', current ? ('Currently marked: ' + STATUS[current].label) : 'Choose an attendance status'));
    var grid = el('div', 'option-grid');
    STATUS_ORDER.forEach(function (k) {
      var b = el('button', 'option-btn', STATUS[k].label);
      b.style.background = STATUS[k].color;
      b.addEventListener('click', function () {
        state.records[key] = k;
        closeModal();
        render();
        saveStatus(key, k).catch(function () {
          delete state.records[key];
          render();
          alert('Could not save that entry. Please try again.');
        });
      });
      grid.appendChild(b);
    });
    box.appendChild(grid);
    var footer = el('div', 'modal-footer');
    var clearBtn = el('button', null, 'Clear entry');
    clearBtn.addEventListener('click', function () {
      var had = state.records[key];
      if (had) {
        delete state.records[key];
        closeModal();
        render();
        saveStatus(key, '').catch(function () {
          state.records[key] = had;
          render();
          alert('Could not clear that entry. Please try again.');
        });
      } else {
        closeModal();
      }
    });
    var cancelBtn = el('button', null, 'Cancel');
    cancelBtn.addEventListener('click', closeModal);
    footer.appendChild(clearBtn);
    footer.appendChild(cancelBtn);
    box.appendChild(footer);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
  }

  function computeStats(y, m) {
    var counts = { WFH: 0, WFO: 0, Leave: 0, Holiday: 0 };
    Object.keys(state.records).forEach(function (key) {
      var parts = key.split('-');
      var ky = parseInt(parts[0], 10), km = parseInt(parts[1], 10) - 1;
      if (ky === y && km === m) counts[state.records[key]] = (counts[state.records[key]] || 0) + 1;
    });
    return counts;
  }

  function downloadUrlFor(scope) {
    var params = new URLSearchParams();
    params.set('scope', scope);
    params.set('year', state.viewYear);
    if (scope === 'month') params.set('month', state.viewMonth + 1);
    return cfg.downloadUrl + '?' + params.toString();
  }

  function render() {
    root.innerHTML = '';

    var card = el('div', 'card');

    var navRow = el('div', 'nav-row');
    var navLeft = el('div', 'nav-left');
    var prevBtn = el('button', 'icon-btn', '\u2039');
    prevBtn.addEventListener('click', function () {
      state.viewMonth -= 1;
      if (state.viewMonth < 0) { state.viewMonth = 11; state.viewYear -= 1; }
      render();
    });
    var monthLabel = el('div', 'month-label', MONTH_NAMES[state.viewMonth] + ' ' + state.viewYear);
    var nextBtn = el('button', 'icon-btn', '\u203A');
    nextBtn.addEventListener('click', function () {
      state.viewMonth += 1;
      if (state.viewMonth > 11) { state.viewMonth = 0; state.viewYear += 1; }
      render();
    });
    navLeft.appendChild(prevBtn);
    navLeft.appendChild(monthLabel);
    navLeft.appendChild(nextBtn);
    navRow.appendChild(navLeft);

    var navRight = el('div', 'nav-left');
    var yearSelect = el('select', 'year-select');
    var baseYear = today.getFullYear();
    for (var yy = baseYear - 4; yy <= baseYear + 1; yy++) {
      var opt = el('option', null, String(yy));
      opt.value = String(yy);
      if (yy === state.viewYear) opt.selected = true;
      yearSelect.appendChild(opt);
    }
    yearSelect.addEventListener('change', function () {
      state.viewYear = parseInt(yearSelect.value, 10);
      render();
    });
    var todayBtn = el('button', 'today-btn', 'Today');
    todayBtn.addEventListener('click', function () {
      state.viewYear = today.getFullYear();
      state.viewMonth = today.getMonth();
      render();
    });
    navRight.appendChild(yearSelect);
    navRight.appendChild(todayBtn);
    navRow.appendChild(navRight);

    card.appendChild(navRow);

    var gridWrap = el('div', 'grid-wrap');
    var weekdayRow = el('div', 'weekday-row');
    WEEKDAYS.forEach(function (w) { weekdayRow.appendChild(el('span', null, w)); });
    gridWrap.appendChild(weekdayRow);

    var dayGrid = el('div', 'day-grid');
    var firstDow = new Date(state.viewYear, state.viewMonth, 1).getDay();
    var daysInMonth = new Date(state.viewYear, state.viewMonth + 1, 0).getDate();
    for (var b = 0; b < firstDow; b++) dayGrid.appendChild(el('div', 'day-cell blank'));
    for (var d = 1; d <= daysInMonth; d++) {
      var key = dateKey(state.viewYear, state.viewMonth, d);
      var status = state.records[key];
      var cls = 'day-cell' + (status ? (' status-' + status) : '') + (key === todayKey ? ' today' : '');
      var cell = el('div', cls);
      cell.appendChild(document.createTextNode(String(d)));
      if (status) {
        var dot = el('span', 'dot');
        dot.style.background = STATUS[status].color;
        cell.appendChild(dot);
      }
      (function (yy2, mm2, dd2) {
        cell.addEventListener('click', function () { openModal(yy2, mm2, dd2); });
      })(state.viewYear, state.viewMonth, d);
      dayGrid.appendChild(cell);
    }
    gridWrap.appendChild(dayGrid);
    card.appendChild(gridWrap);

    var legend = el('div', 'legend');
    STATUS_ORDER.forEach(function (k) {
      var item = el('div', 'legend-item');
      var sw = el('span', 'legend-swatch');
      sw.style.background = STATUS[k].color;
      item.appendChild(sw);
      item.appendChild(document.createTextNode(STATUS[k].label));
      legend.appendChild(item);
    });
    card.appendChild(legend);
    root.appendChild(card);

    var statsCard = el('div', 'card');
    var statsRow = el('div', 'stats-row');
    var counts = computeStats(state.viewYear, state.viewMonth);
    STATUS_ORDER.forEach(function (k) {
      var box = el('div', 'stat-box');
      box.appendChild(el('div', 'num', String(counts[k] || 0)));
      box.appendChild(el('div', 'lbl', k));
      statsRow.appendChild(box);
    });
    statsCard.appendChild(statsRow);
    root.appendChild(statsCard);

    var actionsCard = el('div', 'card');
    var actionsRow = el('div', 'actions-row');
    var downloadMonthBtn = el('a', 'action-btn', 'Download ' + MONTH_NAMES[state.viewMonth] + ' report');
    downloadMonthBtn.href = downloadUrlFor('month');
    var downloadYearBtn = el('a', 'action-btn primary', 'Download ' + state.viewYear + ' full report');
    downloadYearBtn.href = downloadUrlFor('year');
    actionsRow.appendChild(downloadMonthBtn);
    actionsRow.appendChild(downloadYearBtn);
    actionsCard.appendChild(actionsRow);
    root.appendChild(actionsCard);

    var note = el('footer', 'note', 'Entries save automatically to your account.');
    root.appendChild(note);
  }

  render();
})();
