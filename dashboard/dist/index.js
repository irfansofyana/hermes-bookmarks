/* Task 1 hand-written preview; Task 3 owns the shared UI/build outputs. */
(function () {
  'use strict';
  const SDK = window.__HERMES_PLUGIN_SDK__;
  const registry = window.__HERMES_PLUGINS__;
  if (!SDK || !SDK.React || typeof SDK.React.createElement !== 'function' ||
      !registry || typeof registry.register !== 'function') {
    throw new Error('Hermes Bookmarks: Dashboard SDK is unavailable');
  }
  function FoundationPreview() {
    const h = SDK.React.createElement;
    return h('section', { 'aria-label': 'Bookmarks foundation preview' },
      h('h2', null, 'Bookmarks'),
      h('p', { role: 'status' }, 'Foundation preview — saving, search, and Ask Hermes are not yet available.')
    );
  }
  registry.register('hermes-bookmarks', FoundationPreview);
})();
