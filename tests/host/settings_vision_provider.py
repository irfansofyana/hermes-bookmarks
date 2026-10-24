#!/usr/bin/env python3
"""Opt-in real facade attempt against existing main route; NEVER change trust.

No credential files are read/exported by this harness. Public PluginContext
resolves its normal host-owned policy/auth. This constructor-only probe does
not install/register the plugin in the active home, and does not turn denied
access into success. Actual registry evidence is in settings_vision_native.py.
"""
import argparse,asyncio,io,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


async def run(output):
    from hermes_cli.config import load_config
    from hermes_cli.plugins import PluginContext,PluginManifest,get_plugin_manager
    from bookmarks.enrichment import generate,generate_image
    from bookmarks.settings import validate_changes
    from PIL import Image,ImageDraw
    main=load_config().get('model',{})
    provider=main.get('provider') if isinstance(main,dict) else None
    model=(main.get('default') or main.get('model')) if isinstance(main,dict) else None
    report={'real_facade_attempt':True,'active_installation_changed':False,'trust_changed':False,
        'credential_read_or_export_by_harness':False,'registered_active_plugin':False,
        'input_is_synthetic':True,'provider_success_verified':False,
        'retry_disclosure':'One facade call may cause multiple host provider attempts/fallback; no plugin no-retry promise.', 'checks':[]}
    if not provider or not model:
        report['blocker']='Existing public main configuration did not supply an explicit provider/model route.'
    else:
        route={'provider':provider,'model':model,'owner_profile':'default'}
        validate_changes(route,allow_owner=True)
        report['route']={'provider':provider,'model':model}
        ctx=PluginContext(PluginManifest(name='hermes-bookmarks'),get_plugin_manager())
        image=Image.new('RGB',(160,120),'white');draw=ImageDraw.Draw(image);draw.ellipse((55,25,125,95),fill='blue');draw.rectangle((8,8,32,32),fill='red');out=io.BytesIO();image.save(out,format='PNG');content=out.getvalue()
        text='Synthetic engineering note: a small team tests a revision-checked bookmark store. Manual notes stay separate from generated summaries. The team verifies durable request receipts before retrying uncertain operations.'
        for lane in ('text','image'):
            try:
                operation=generate(ctx.llm,text,route,'https://example.org/synthetic-provider-probe') if lane=='text' else generate_image(ctx.llm,content,'image/png',route)
                result=await asyncio.wait_for(operation,timeout=120)
                fact=lane=='text' or ('blue' in result['summary'].lower() and ('circle' in result['summary'].lower() or 'round' in result['summary'].lower()))
                report['checks'].append({'lane':lane,'state':'succeeded' if fact else 'semantic_verification_failed','actual_provider':result['provider'],'actual_model':result['model'],'coverage':result['coverage'],'summary':result['summary'],'tags':result['tags'],'visual_fact_verified':fact if lane=='image' else None})
            except PermissionError as error:
                report['checks'].append({'lane':lane,'state':'blocked','error_code':'trust_denied','error_type':type(error).__name__})
            except Exception as error:
                report['checks'].append({'lane':lane,'state':'blocked','error_code':'provider_or_validation_unavailable','error_type':type(error).__name__})
        report['provider_success_verified']=len(report['checks'])==2 and all(row['state']=='succeeded' for row in report['checks'])
        if not report['provider_success_verified']:report['blocker']='Existing unmodified host policy/route did not verify both lanes; no fabricated result, credential copy, override grant or SDK fallback used.'
    Path(output).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--allow-synthetic-provider-attempt',action='store_true');a=p.parse_args()
    if not a.allow_synthetic_provider_attempt:p.error('Explicit provider-attempt opt-in required')
    asyncio.run(run(a.output))
