const {test} = require('node:test');
const assert = require('node:assert/strict');
const {create} = require('../static/processing-stream.js');

test('batched progress stays ordered and completion waits for every visible step', async () => {
  let clock = 0;
  const shown = [];
  const queue = create({onStep: step => shown.push({step, time: clock}), interval: 300,
    now: () => clock, wait: async ms => { clock += ms; }});
  queue.push('received'); queue.push('checked'); queue.push('complete');
  assert.equal(shown.length, 0);
  await queue.flush();
  assert.deepEqual(shown, [
    {step: 'received', time: 0}, {step: 'checked', time: 300}, {step: 'complete', time: 600}
  ]);
});

test('naturally spaced network events are displayed without an extra delay', async () => {
  let clock = 0;
  const shown = [], waits = [];
  const queue = create({onStep: step => shown.push(step), interval: 300,
    now: () => clock, wait: async ms => { waits.push(ms); clock += ms; }});
  queue.push('first'); await queue.flush();
  clock = 500;
  queue.push('second'); await queue.flush();
  assert.deepEqual(shown, ['first', 'second']);
  assert.deepEqual(waits, []);
});

test('cancellation prevents queued progress from appearing after an interrupted run', async () => {
  const shown = [];
  let release;
  const queue = create({onStep: step => shown.push(step), now: () => 0,
    wait: () => new Promise(resolve => { release = resolve; })});
  queue.push('first'); await queue.flush();
  queue.push('second');
  await Promise.resolve();
  queue.cancel(); release();
  await queue.flush();
  assert.deepEqual(shown, ['first']);
});

test('a slow step renderer cannot reorder a later chunk', async () => {
  let clock = 0;
  const shown = [];
  const queue = create({onStep: step => { shown.push(step); clock += 40; },
    interval: 120, now: () => clock, wait: async ms => { clock += ms; }});
  queue.push(1); queue.push(2);
  await queue.flush();
  queue.push(3); await queue.flush();
  assert.deepEqual(shown, [1, 2, 3]);
  assert.equal(clock, 360);
});
