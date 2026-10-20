function createLibrary(React, adapter, components, styles) {
  const {createElement: h, useState, useEffect, useRef} = React;
  const Button = components.Button || 'button';
  const Input = components.Input || 'input';
  const view = {query: '', url: '', scroll: 0};
  return function Bookmarks({ctx} = {}) {
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState('');
    const [asset, setAsset] = useState(null), [uploading, setUploading] = useState(false);
    const uploadBusy = useRef(false);
    const [query, setQuery] = useState(view.query);
    const [ask, setAsk] = useState(null);
    const [preparing, setPreparing] = useState(false);
    const handoffBusy = useRef(false);
    const surface = useRef(null);
    const busy = useRef(false), generation = useRef(0), alive = useRef(true);
    const form = useRef(null);
    useEffect(() => { if (surface.current) surface.current.scrollTop = view.scroll; }, [loading]);
    async function prepareChat() {
      if (!ask || handoffBusy.current) return;
      handoffBusy.current = true; setPreparing(true);
      view.url = form.current?.elements.url.value || '';
      const result = await adapter.chat.prepare({target:ask.target,itemIds:[ask.id],prompt:'Help me explore this saved bookmark.',append:true});
      if (alive.current) {
        setPreparing(false);
        if (!result.ok) setError('Native chat could not accept this context (' + result.reason + '). Open the intended conversation and try again.');
        else { setAsk(null); setNotice('References appended to the native draft. Nothing was sent.'); }
      }
      handoffBusy.current = false;
    }
    async function load(term) {
      const version = ++generation.current;
      setLoading(true);
      try {
        const payload = await adapter.request(ctx, '/items?query=' + encodeURIComponent(term));
        if (!payload.ok) throw Error(payload.error.message);
        if (alive.current && version === generation.current) {
          setItems(payload.result.items); setTotal(payload.result.total); setError('');
        }
      } catch (e) {
        if (alive.current && version === generation.current) setError('Could not load the library. Check configuration and try again.');
      } finally {
        if (alive.current && version === generation.current) setLoading(false);
      }
    }
    useEffect(() => { alive.current = true; load(query); return () => {alive.current = false; generation.current++;}; }, [query]);
    async function save(e) {
      e.preventDefault();
      if (busy.current) return;
      const url = e.currentTarget.elements.url.value;
      if (!url) return;
      busy.current = true; setSaving(true); setError(''); setNotice('');
      try {
        const payload = await adapter.request(ctx, '/items', {method: 'POST', body: {url}});
        if (!payload.ok) throw Error(payload.error.message);
        if (alive.current) {
          if (form.current?.elements.url.value === url) {form.current.elements.url.value = ''; view.url = '';}
          setNotice('Saved to your library.'); load(query);
        }
      } catch (e) {
        if (alive.current) setError('Bookmark save failed. Your URL is preserved; check configuration and try again.');
      } finally {
        busy.current = false; if (alive.current) setSaving(false);
      }
    }
    async function uploadImage(event) {
      const file=event.currentTarget.files?.[0];
      if (!file || uploadBusy.current) return;
      if (file.size>10*1024*1024 || !['image/png','image/jpeg','image/webp'].includes(file.type)) {
        setError('Choose a PNG, JPEG, or WebP image up to 10 MiB.'); return;
      }
      uploadBusy.current=true; setUploading(true); setError('');
      try {
        const bytes=new Uint8Array(await file.arrayBuffer());
        let binary='';
        for (let i=0;i<bytes.length;i+=32768) binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
        const payload=await adapter.request(ctx,'/assets/base64',{method:'POST',body:{mime_type:file.type,content_base64:btoa(binary)}});
        if (!payload.ok) throw Error('Upload rejected');
        if (alive.current) {setAsset(payload.result); setNotice('Image saved as asset ' + payload.result.id + '. No AI analysis was requested.');}
        try {
          const preview=await adapter.request(ctx,'/assets/'+payload.result.id+'/preview');
          if (!preview.ok) throw Error('Preview unavailable');
          if (alive.current) setAsset({...payload.result,preview:preview.result});
        } catch (_) {if (alive.current) setNotice('Image is saved as asset '+payload.result.id+'. Preview is unavailable.');}
      } catch (_) {if (alive.current) setError('Image upload failed. Check the image and library configuration.');}
      finally {uploadBusy.current=false; if (alive.current) setUploading(false);}
    }
    return h('section', {className: 'hb-library', 'aria-label': 'Bookmarks', ref:surface, onScroll:e=>{view.scroll=e.currentTarget.scrollTop;}},
      h('style', null, styles),
      h('header', {className: 'hb-header'},
        h('div', null, h('p', {className: 'hb-eyebrow'}, 'BOOKMARKS / SHARED LIBRARY'), h('h1', null, 'A place for what matters.'),
          h('p', {className: 'hb-subtitle'}, 'Save a link now. Find it when you need it.')),
        h('span', {className: 'hb-preview'}, 'Foundation preview')),
      h('form', {className: 'hb-capture', ref: form, onSubmit: save, 'data-capture': true},
        h('label', {htmlFor: 'hb-url'}, 'Add to your library'),
        h('div', {className: 'hb-input-row'}, h(Input, {id: 'hb-url', name: 'url', type: 'url', required: true, maxLength: 8192,
          placeholder: 'Paste a link…', 'aria-label': 'Bookmark URL', disabled: saving, defaultValue:view.url, onInput:e=>{view.url=e.currentTarget.value;}}),
          h(Button, {type: 'submit', disabled: saving}, saving ? 'Saving…' : 'Save link')),
        h('p', {className:'hb-footer'}, 'When enrichment is configured, saving queues page text for your library model. Provider charges may apply.')),
      h('div', {className:'hb-capture'},
        h('label', {htmlFor:'hb-image'}, uploading ? 'Uploading image…' : 'Add an image attachment'),
        h('input', {id:'hb-image',type:'file',accept:'image/png,image/jpeg,image/webp',disabled:uploading,onChange:uploadImage}),
        asset && h('div', null,
          asset.preview && h('img', {alt:'Uploaded image preview',src:'data:'+asset.preview.mime_type+';base64,'+asset.preview.content_base64,style:{maxWidth:'100%',maxHeight:160}}),
          h('p', {className:'hb-footer'}, 'Asset '+asset.id+' · '+asset.width+' × '+asset.height+' · image items and note embedding arrive in M3.'))),
      error && h('div', {role: 'alert', className: 'hb-error'}, error, h(Button, {type: 'button', onClick: () => load(query)}, 'Retry')),
      notice && h('p', {role: 'status', className: 'hb-notice'}, notice),
      h('div', {className: 'hb-toolbar'}, h('h2', null, query ? 'Search results' : 'All bookmarks'),
        h('form', {onSubmit: e => {e.preventDefault(); view.query = e.currentTarget.elements.query.value; setQuery(view.query);}},
          h(Input, {name: 'query', type: 'search', defaultValue:view.query, placeholder: 'Search your library', 'aria-label': 'Search bookmarks'}),
          h(Button, {type: 'submit'}, 'Search'))),
      h('p', {className: 'hb-count', role: 'status'}, loading ? 'Loading your library…' : `${total} saved ${total === 1 ? 'link' : 'links'}`),
      !loading && !error && items.length === 0 && h('div', {className: 'hb-empty'},
        h('h3', null, query ? 'No matches yet' : 'Your next good idea starts here'),
        h('p', null, query ? 'Try a title, domain, or a different search.' : 'Paste an article, a repository, or a link worth keeping.')),
      h('ul', {className: 'hb-items'}, items.map(item => h('li', {key: item.id},
        h('div', {className: 'hb-item-mark', 'aria-hidden': true}, '↗'),
        h('div', {className: 'hb-item-body'},
          h('a', {href: item.url, target: '_blank', rel: 'noopener noreferrer'}, item.title || item.url),
          h('p', null, new URL(item.url).hostname)),
        h('span', {className: 'hb-item-status'}, ({succeeded:'Summary saved',pending:'Enrichment queued',running:'Enriching…',failed:'Enrichment failed',cancelled:'Cancelled'})[item.enrichment_status] || 'AI not connected'),
        h(Button, {type:'button', disabled:!adapter.chat?.snapshot(), title:'Prepare bookmark references in native Hermes chat', onClick:()=>setAsk({id:item.id,target:adapter.chat.snapshot()})}, 'Ask Hermes')))),
      ask && h('aside', {className:'hb-capture', 'aria-label':'Native chat context'},
        h('p', null, 'Append bookmark references to ' + ask.target.owner.profile + ' / ' + ask.target.sessionId + '. Existing draft text is kept. Nothing is sent automatically.'),
        h(Button, {type:'button', disabled:preparing, onClick:prepareChat}, preparing ? 'Preparing…' : 'Append to native draft'),
        h(Button, {type:'button', onClick:()=>setAsk(null)}, 'Cancel')),
      h('footer', {className: 'hb-footer'}, 'Native chat uses your Hermes session. Context handoff is unavailable without a supported target (including the current Dashboard SDK). Enrichment requires a configured owner/model and a running host supervisor. Image attachments do not yet appear as standalone library items.'));
  };
}
