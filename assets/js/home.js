/* 첫 화면: 표지 전시 멈춤/재생. 마우스를 올리거나 표지에 초점이 가도 CSS가 멈춘다. */
(function () {
  var mq = document.querySelector('[data-marquee]');
  var btn = document.querySelector('[data-marquee-toggle]');
  if (!mq || !btn) return;
  btn.addEventListener('click', function () {
    var paused = !mq.hasAttribute('data-paused');
    mq.toggleAttribute('data-paused', paused);
    btn.classList.toggle('is-paused', paused);
    btn.textContent = paused ? '재생' : '멈춤';
  });
  /* 탭으로 가려진 표지에 초점이 가면 브라우저가 상자를 옆으로 밀어 둔다. 초점이 빠지면 되돌려 끊김 없이 다시 돈다. */
  mq.addEventListener('focusout', function () {
    setTimeout(function () { if (!mq.contains(document.activeElement)) mq.scrollLeft = 0; }, 0);
  });
})();
