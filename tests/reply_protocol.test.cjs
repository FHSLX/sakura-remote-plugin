const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
const projection = source.slice(source.indexOf('function segmentsFromReply('), source.indexOf('async function readImage('));
const context = vm.createContext({ state: { characterId: 'sakura' } });
vm.runInContext(projection, context);

test('audio identity preserves source indexes after empty display segments are removed', () => {
  const result = context.segmentsFromReply({ character_id: 'sakura', historyEntryId: 'reply-1', segments: [
    { segmentIndex: 0, raw_content: '', content: '' },
    { segmentIndex: 1, raw_content: 'spoken', content: 'translated', suppressTts: true,
      control: { resourceId: 'portrait', payload: { key: 'happy' } } },
    { segmentIndex: 3, raw_content: 'last', content: 'last' },
  ] });
  assert.equal(result.length, 2);
  assert.equal(result[0].historyEntryId, 'reply-1');
  assert.equal(result[0].segmentIndex, 1);
  assert.equal(result[0].suppressTts, true);
  assert.equal(result[0].portrait, 'happy');
  assert.equal(result[1].segmentIndex, 3);
});

test('legacy reply fields keep the original array index and portrait label', () => {
  const result = context.segmentsFromReply({ segments: [null, { raw_content: 'spoken', portrait: 'smile' }] });
  assert.equal(result[0].segmentIndex, 1);
  assert.equal(result[0].portrait, 'smile');
  assert.equal(result[0].characterId, 'sakura');
});
