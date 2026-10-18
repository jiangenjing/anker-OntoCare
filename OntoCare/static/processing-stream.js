/* Pace genuine server progress events even when the transport batches them. */
(function (root) {
  function create({onStep, interval = 300, now = Date.now,
    wait = ms => new Promise(resolve => setTimeout(resolve, ms))}) {
    let tail = Promise.resolve(), lastShown = null, cancelled = false;
    return {
      push(event) {
        tail = tail.then(async () => {
          if (cancelled) return;
          const remaining = lastShown === null ? 0 : interval - (now() - lastShown);
          if (remaining > 0) await wait(remaining);
          if (cancelled) return;
          onStep(event);
          lastShown = now();
        });
        return tail;
      },
      flush() { return tail; },
      cancel() { cancelled = true; }
    };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {create};
  else root.OntoProcessing = {create};
})(typeof window === 'undefined' ? this : window);
