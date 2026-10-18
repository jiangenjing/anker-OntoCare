const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function fixture() {
  const nodes = new Map(), notices = [], requests = [], submissions = [];
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, {id, value: '', hidden: false, disabled: false,
      textContent: '', dataset: {}, files: [], listeners: {},
      addEventListener(name, fn) { this.listeners[name] = fn; },
      replaceChildren(...items) { this.children = items; if (id === 'media-model') this.value = items[0]?.value || ''; },
      setAttribute() {}, append() {}, focus() {},
      parentElement: {before(item) { notices.push(item); }}
    });
    return nodes.get(id);
  }
  const dialog = node('customerMedia');
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; dialog.listeners.close(); };
  const open = node('openMedia'); open.dataset.openMedia = 'image';
  const close = node('closeMedia');
  node('media-op').value = 'text';
  const models = ['nova','glm','deepseek-pro','qwen','kimi','deepseek-flash','asr','tts','seedream']
    .map(id => ({id, name: id, model: 'test/' + id}));
  let resolveRun;
  const context = {
    console, sending: false, mediaUploading: false, send: () => submissions.push(node('in').value),
    document: {getElementById: node, createElement: tag => node('created-' + tag),
      querySelectorAll: () => [open], querySelector: selector => selector === '[data-close-media]' ? close : null},
    window: {addEventListener() {}},
    OntoVoice: {create(options) { return {cancel() { options.onState({status: 'idle'}); }}; }},
    Option: function (text, value) { this.text = text; this.value = value; },
    fetch: async (url, options) => {
      requests.push({url, options});
      if (!options?.method) return {ok: true, json: async () => ({catalog: {models, configured: false}})};
      return new Promise(resolve => { resolveRun = result => resolve({ok: true, json: async () => result}); });
    }
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(require.resolve('../static/models.js'), 'utf8'), context);
  return {node, dialog, requests, notices, submissions, open: () => open.listeners.click(),
    complete: result => resolveRun(result)};
}

test('closing and reopening a pending operation cannot reset it or start a duplicate', async () => {
  const f = fixture(); await f.open();
  f.node('media-op').value = 'text'; f.node('media-op').onchange();
  f.node('media-prompt').value = '界面测试';
  const pending = f.node('media-run').onclick();
  assert.equal(f.node('media-op').disabled, true);
  f.dialog.close(); await f.open();
  assert.equal(f.node('media-op').value, 'text');
  assert.equal(f.node('media-op').disabled, true);
  await f.node('media-run').onclick();
  assert.equal(f.requests.filter(request => request.options?.method === 'POST').length, 1);
  f.complete({status: 'OK', text: '测试识别文字', model_name: 'Test'}); await pending;
  assert.equal(f.node('media-run').disabled, false);
  assert.equal(f.node('media-result').value, '测试识别文字');
});

test('explicit Agent handoff preserves the existing automatic send flow and original question', async () => {
  const f = fixture(); await f.open();
  f.node('media-op').value = 'text'; f.node('media-op').onchange();
  const pending = f.node('media-run').onclick();
  f.complete({status: 'OK', text: '候选观察', model_name: 'Test'}); await pending;
  f.node('in').value = '原来的问题';
  f.node('media-useDraft').onclick();
  assert.match(f.node('in').value, /^原来的问题\n待核验模型观察/);
  assert.match(f.node('in').value, /候选观察/);
  assert.equal(f.dialog.open, false);
  assert.match(f.notices[0].textContent, /已将多模态文字提交客服 Agent/);
  assert.equal(f.submissions.length, 1);
  assert.equal(f.submissions[0], f.node('in').value);
  assert.equal(f.requests.filter(request => request.url === '/api/chat/stream').length, 0);
});
