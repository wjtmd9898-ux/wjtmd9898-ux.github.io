/* PDF.js로 문서를 쪽 단위로 보여 준다. [data-pdfv] 요소마다 하나씩 붙는다.
   필요한 마크업: data-src(PDF 경로), .pdfv__prev, .pdfv__next, .pdfv__stage, .pdfv__now, .pdfv__total */
(function () {
  var WORKER = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  function mount(root) {
    if (!window.pdfjsLib) return;
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER;
    var src = root.getAttribute('data-src');
    var stage = root.querySelector('.pdfv__stage');
    var status = root.querySelector('.pdfv__status');
    var prev = root.querySelector('.pdfv__prev');
    var next = root.querySelector('.pdfv__next');
    var now = root.querySelector('.pdfv__now');
    var total = root.querySelector('.pdfv__total');
    var canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    stage.appendChild(canvas);
    var doc = null, page = 1, busy = false, queued = null;
    var start = parseInt(new URLSearchParams(location.search).get('p') || '1', 10);
    if (root.hasAttribute('data-follow-url') && start > 0) page = start;

    function pad(n) { return (n < 10 ? '0' : '') + n; }

    function render(n) {
      if (busy) { queued = n; return; }
      busy = true;
      doc.getPage(n).then(function (pg) {
        var base = pg.getViewport({ scale: 1 });
        var w = stage.clientWidth || base.width;
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        var vp = pg.getViewport({ scale: (w / base.width) * dpr });
        canvas.width = Math.floor(vp.width);
        canvas.height = Math.floor(vp.height);
        return pg.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;
      }).then(function () {
        busy = false;
        if (status) status.hidden = true;
        now.textContent = pad(n);
        prev.disabled = n <= 1;
        next.disabled = n >= doc.numPages;
        stage.setAttribute('aria-label', doc.numPages + '쪽 중 ' + n + '쪽');
        if (queued !== null) { var q = queued; queued = null; render(q); }
      }).catch(function () { busy = false; });
    }

    function go(d) {
      if (!doc) return;
      var n = Math.max(1, Math.min(doc.numPages, page + d));
      if (n === page) return;
      page = n;
      render(page);
      if (root.hasAttribute('data-follow-url')) {
        var u = new URL(location.href); u.searchParams.set('p', page); history.replaceState(null, '', u);
      }
    }

    prev.addEventListener('click', function () { go(-1); });
    next.addEventListener('click', function () { go(1); });
    root.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { go(-1); e.preventDefault(); }
      if (e.key === 'ArrowRight') { go(1); e.preventDefault(); }
    });
    if (root.hasAttribute('data-global-keys')) {
      document.addEventListener('keydown', function (e) {
        if (e.target.closest('input, textarea')) return;
        if (e.key === 'ArrowLeft') go(-1);
        if (e.key === 'ArrowRight') go(1);
      });
    }

    var t = null;
    window.addEventListener('resize', function () {
      clearTimeout(t); t = setTimeout(function () { if (doc) render(page); }, 150);
    });

    window.pdfjsLib.getDocument(src).promise.then(function (d) {
      doc = d;
      total.textContent = pad(d.numPages);
      if (page > d.numPages) page = 1;
      render(page);
    }).catch(function () {
      if (status) status.textContent = '문서를 불러오지 못했습니다. 아래 링크로 PDF를 여세요.';
    });
  }

  document.querySelectorAll('[data-pdfv]').forEach(mount);
})();
