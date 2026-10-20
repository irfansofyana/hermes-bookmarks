function createNativeChat(host) {
  function snapshot() {
    const id = host?.state?.focusedStoredSessionId?.get?.();
    const owner = host?.state?.focusedSessionOwner?.get?.();
    return typeof id === 'string' && owner?.connectionId && owner?.profile
      ? {sessionId:id, owner:{connectionId:owner.connectionId,profile:owner.profile}} : null;
  }
  function same(target) {
    const current = snapshot();
    return current && target && current.sessionId === target.sessionId &&
      current.owner.connectionId === target.owner?.connectionId && current.owner.profile === target.owner?.profile;
  }
  return {snapshot, async prepare({target,itemIds,prompt,append=false} = {}) {
    const fail = reason => ({ok:false,reason});
    if (!host?.composer?.getDraft || !host?.composer?.insertText || !host?.openSession || !host?.profileRoutes) return fail('unsupported');
    if (!Array.isArray(itemIds) || !itemIds.length || itemIds.length > 20 ||
        itemIds.some(id => typeof id !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(id)) ||
        typeof prompt !== 'string' || !prompt.trim() || prompt.length > 2000) return fail('invalid_context');
    if (!same(target)) return fail('target_changed');
    try {
      const routes = await host.profileRoutes();
      const route = routes.find(r => r.connectionId === target.owner.connectionId && r.targetProfile === target.owner.profile);
      if (!route) return fail('route_unavailable');
      if (!same(target)) return fail('target_changed');
      await host.openSession(target.sessionId, {route, awaitHydration:true});
      if (!same(target)) return fail('target_changed');
      const draft = await host.composer.getDraft(target.sessionId);
      if (!same(target)) return fail('target_changed');
      if (draft && !append) return fail('draft_not_empty');
      // Always insert, never set/replace. User typing after the lookup is kept.
      const text = prompt.trim() + '\n\nSaved bookmark IDs (use bookmark_get for details):\n' + itemIds.map(id => '- ' + id).join('\n');
      const applied = await host.composer.insertText(target.sessionId, text, {mode:'block'});
      return applied ? {ok:true} : fail('composer_unavailable');
    } catch (e) { return fail('native_handoff_failed'); }
  }};
}
