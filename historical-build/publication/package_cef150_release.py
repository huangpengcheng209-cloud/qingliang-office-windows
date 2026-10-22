"""Publish the one tested staging runtime and corresponding tracked-source snapshot."""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path
import psutil

TASK=Path(r'D:\CodexWorkspaces\2026-10-13\office-windows')
STAGE=Path(r'D:\CodexCache\office-windows')
APP=STAGE/'candidate/app'
FINAL=TASK/'release/Office-Windows-x64'
VERSION='9.4.0.129-win.22'
SCOPE='''# 氢量办公 Windows 修改版 9.4.0.129-win.22

本修改版基于 ONLYOFFICE 9.4.0.129，原软件由 Ascensio System SIA 开发。显示发布者为个人开发者，修改日期 2026-10-16；保留上游标识、版权和许可。当前为未签名的内部验收候选，尚未公开发布。

本版修复表格在脚注高度增加、回退到较早行重排时沿用上一轮溢出标志，导致提前换页和大片单元格留白的问题。每次重排行重新计算换页状态。诊断样本中脚注占用增加约 8.3 毫米后从第 19 行退回第 16 行，旧版仍保留换页标志；修复后第 17/18 行回到第一页，脚注及引用在第二页完整保留。仍有少量标记落页与 WPS 不同，不宣称全部脚注/合并分页等同参考。

更正 win.20 超高行比较：WPS COM 在两个受保护超高行控制中导入正文含 150 标记，但 PDF 只有前 35 个；取消禁止拆分的参考副本可导出全部 150 个。氢量办公 5/6 页保留完整内容，不能以不完整参考的 2/3 页作为正确目标。此判断限于上述控制及 COM 导出路径。

候选及安装版检查十五组脚注/嵌套组合、八组合并控制、既有八组行控制、四份组合文档和三份复杂 DOCX 的实际保存重开、四类基础流程。实际结果以 evidence/win22-release-acceptance.json 及 publication/win22脚注回退换页修复验收.md 为准。所有新增样本是合成控制，未完成真实业务文件、四小时混合会话或跨机打印验收。原生转换器及保存事务沿用 win.21，历史检查保持原版本身份。

既有修改继续保留：CEF 150 / Chromium 150 适配、中文简洁界面、文件面板和功能搜索、旧 DOC 边框作用范围/颜色/缩进修复、Windows RTF 和 XLS 转换修复、PDF 字体及文字保存、本地帮助回退。编辑器界面默认简体中文，离线帮助内容目前主要为英语。

Windows 普通单文件保存和另存使用完整临时写入、刷新后替换，失败不退回原地截断写入，保留失败未保存状态。只读/占用目标明确拒绝；硬链接目标不支持此保存路径。被结束的准备过程可能留下临时文件；替换和回滚均失败时保留备份和新结果，尚无自动恢复/清理界面。图片目录导出不属于此事务。

保留已修复的后台模板转换退出取消、浏览器异步创建前关闭请求交接。历史其他 PPTX 打开超时或进程残留是否同源仍未证明。后续循环通过不等于全部历史异常已解决。

CSV 无列类型定义。默认导入保留已覆盖的前导零编号和 20 位整数文本，普通数量及小数仍按数值处理；不能把数值显示格式与逐字符原文保真混同。中文 GBK 导入需要选择相应编码；其内部索引为 18，Windows 代码页 936 不是此参数的有效索引。PDF 基础验收中的文字批注不代表 PDF 正文编辑全面通过。

采用单一 D 盘构建 staging，Windows 重建组件和五个转换器 V8 快照与源代码包分别核验。未修改的支持库仍来自固定官方 Windows 基线，不宣称全部依赖已从源码重建。对应源码包为 source/Office-Windows-pinned-sources.zip；上游固定版本、累计补丁、构建及验收工具随材料保留。

安装器按用户选择保持未签名，不注册默认文件关联，不安装更新服务。默认建议使用当前用户可写的独立目录。Start-Chinese.cmd 默认禁用 AI 并使用软件渲染；配置、临时文件和文档恢复数据位于该安装目录内。不要把缓存检查当成清洁设备安装或真实打印验收。

尚待更多真实业务文件、复杂分页/边框交点的逐页对照、至少四小时混合会话、更多跨行合并组合、真实存储故障、网络/云盘、干净 Windows 设备，以及完整依赖对应源码和实际对外下载地址。单机合成样本通过不代表全面兼容 WPS，也不代表当前已具备公开发行的全部条件。
'''

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(name):return json.loads((TASK/'evidence'/name).read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
def not_running():
    roots=[APP, FINAL/'app', STAGE/'installed-test/app']
    assert not any(any((p.info['exe'] or '').lower().startswith(str(root).lower()+'\\') for root in roots) for p in psutil.process_iter(['exe'])), 'Close task editor before packaging'

def verify_components():
    rows=[]
    sources={
        'editors.exe':'desktop-apps/win-linux/build/win_64/DesktopEditors.exe',
        'ascdocumentscore.dll':'core/build/lib/win_64/ascdocumentscore.dll',
        'qtascdocumentscore.dll':'core/build/lib/win_64/qtascdocumentscore.dll',
        'editors_helper.exe':'core/build/bin/win_64/editors_helper.exe',
        'converter/x2t.exe':'core/build/bin/win_64/x2t.exe',
        'converter/PdfFile.dll':'core/build/lib/win_64/PdfFile.dll',
        'converter/DocxRenderer.dll':'core/build/lib/win_64/DocxRenderer.dll'}
    for target,source in sources.items():
        src=STAGE/'upstream/DesktopEditors'/source
        assert sha(src)==sha(APP/target),(target,'Build output mismatch')
        rows.append({'path':'app/'+target,'sha256':sha(src),'origin':'windows-native-source-rebuild'})
    sdk=STAGE/'upstream/DesktopEditors/sdkjs'
    for editor in ('word','cell','slide','visio'):
        report=read(editor+'-sdk-build.json')
        assert report['exit']==0 and report['node_syntax_checked']
        for relative,h in report['inputs'].items():assert sha(sdk/relative)==h,relative
        for filename,h in report['outputs'].items():
            src=Path(filename);target=APP/'editors/sdkjs'/editor/src.name
            assert sha(src)==h==sha(target),str(target)
            rows.append({'path':'app/'+target.relative_to(APP).as_posix(),'sha256':h,'origin':'windows-sdk-source-build'})
    for report in read('web-controllers-build.json'):
        for record in (report,report['postload']):
            assert all(sha(Path(p))==h for p,h in record['inputs'].items())
            src=Path(record['output']);target=APP/'editors/web-apps/apps'/src.relative_to(STAGE/'build/web-apps')
            assert sha(src)==record['output_sha256']==sha(target)
            rows.append({'path':'app/'+target.relative_to(APP).as_posix(),'sha256':sha(target),'origin':'windows-frontend-source-build'})
    api=read('cef150-documents-api-build.json');assert sha(Path(api['source']))==api['source_sha256']
    assert sha(Path(api['output']))==api['output_sha256']==sha(Path(api['candidate']))
    rows.append({'path':'app/'+Path(api['candidate']).relative_to(APP).as_posix(),'sha256':api['output_sha256'],'origin':'windows-documents-api-source-build'})
    for row in read('cef150-editor-sdk-integration.json')['snapshots']:
        p=Path(row['file']);assert sha(p)==row['sha256']
        rows.append({'path':'app/'+p.relative_to(APP).as_posix(),'sha256':row['sha256'],'origin':'windows-converter-v8-snapshot'})
    for row in read('cef150-runtime-integration.json')['files']:
        if row['origin']=='official-cef150-runtime':
            assert sha(APP/row['path'])==row['sha256'],row['path']
    return rows

def sources():
    repos=read('source-preparation.json');patches=TASK/'source-changes';lock=[]
    for row in repos:
        root=Path(row['path'])
        assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==row['revision']
        subprocess.run(['git','-C',str(root),'diff','--check','HEAD'],check=True,capture_output=True)
        diff=subprocess.check_output(['git','-C',str(root),'diff','--binary','HEAD'])
        if diff:(patches/(row['repository']+'.patch')).write_bytes(diff)
        lock.append({'repository':row['repository'],'revision':row['revision'],'url':subprocess.check_output(['git','-C',str(root),'remote','get-url','origin'],text=True).strip()})
    write(TASK/'source/repositories.lock.json',lock)
    sys.path.insert(0,str(TASK/'scripts'))
    import package_windows_release as p
    p.SCOPE=SCOPE;p.save_source_archive(repos,TASK/'source',patches)

def notices():
    bundle=TASK/'publication/runtime-notice-bundle';cef=bundle/'ThirdPartyLicenses/CEF'
    for srcname,dstname in (('LICENSE.txt','LICENSE.txt'),('README.txt','README.txt'),('CHROMIUM-CREDITS.offline.html','CHROMIUM-CREDITS.html')):
        shutil.copyfile(TASK/'publication/cef150-notices'/srcname,cef/dstname)
    text=(bundle/'OPEN_SOURCE_NOTICES.md').read_text(encoding='utf-8')
    text=text.replace('CEF 109.1.18 / Chromium 109.0.5414.120','CEF 150.0.22 / Chromium 150.0.7871.256').replace('351 个组件','762 个组件')
    (bundle/'OPEN_SOURCE_NOTICES.md').write_text(text,encoding='utf-8')
    paths=[TASK/'source/Office-Windows-pinned-sources.zip']
    paths += [p for p in (TASK/'source/third-party').rglob('*') if p.is_file() and p.suffix.lower() in ('.zip','.7z','.xz','.bz2','.patch') and 'cef-f1c41' not in p.name]
    write(bundle/'SOURCE_MATERIALS.json',{'version':VERSION,'status':'local review materials; external source offer and full dependency closure pending','archives':[{'path_in_handoff':p.relative_to(TASK).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]})

def runtime(rows):
    not_running()
    # Exclude logs and the superseded CEF 109 snapshot; converter snapshots are separate.
    excluded={'console.log','debug.log','snapshot_blob.bin'}
    desired=set()
    for src in APP.rglob('*'):
        if not src.is_file() or src.relative_to(APP).as_posix() in excluded:continue
        relative=src.relative_to(APP);dst=FINAL/'app'/relative;desired.add(dst.relative_to(FINAL).as_posix())
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        assert sha(src)==sha(dst),str(relative)
    pristine=STAGE/'baseline/Office-Win11-x64/samples'
    for src in pristine.rglob('*'):
        if src.is_file():
            dst=FINAL/'samples'/src.relative_to(pristine);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
            desired.add(dst.relative_to(FINAL).as_posix())
    for folder in ('app','samples'):
        for dst in (FINAL/folder).rglob('*'):
            if dst.is_file() and dst.relative_to(FINAL).as_posix() not in desired:
                assert dst.resolve().is_relative_to(FINAL.resolve()),'Cleanup outside final runtime'
                dst.unlink()
    shutil.copytree(TASK/'publication/runtime-notice-bundle',FINAL,dirs_exist_ok=True)
    shutil.copyfile(STAGE/'upstream/DesktopEditors/LICENSE',FINAL/'LICENSE.txt')
    (FINAL/'BUILD_SCOPE.md').write_text(SCOPE,encoding='utf-8')
    (FINAL/'Start-Chinese.cmd').write_bytes(b'@echo off\r\nset "OFFICE_USER_DATA_ROOT=%~dp0user-data"\r\nset "TEMP=%~dp0temp"\r\nset "TMP=%~dp0temp"\r\nif not exist "%TEMP%" mkdir "%TEMP%"\r\nstart "" "%~dp0app\\DesktopEditors.exe" --disable-ai=1 --disable-gpu=1 %*\r\n')
    (FINAL/'启动氢量办公.cmd').write_bytes((FINAL/'Start-Chinese.cmd').read_bytes())
    for row in rows:assert sha(FINAL/row['path'])==row['sha256']
    manifest=[{'path':p.relative_to(FINAL).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(FINAL.rglob('*')) if p.is_file() and p.name!='manifest.sha256.json' and p.relative_to(FINAL).parts[0] not in ('user-data','temp')]
    write(FINAL/'manifest.sha256.json',manifest)
    write(TASK/'evidence/cef150-final-package.json',{'product_name':'氢量办公','version':VERSION,'runtime':str(FINAL),'files':len(manifest),'bytes':sum(r['bytes'] for r in manifest),'rebuilt_components_and_snapshots':rows,'source_snapshot':json.loads((TASK/'source/source-snapshot.json').read_text()),'candidate_runtime_bytes_verified':True,'installer_acceptance':'pending','production_signing':False,'release_ready':False})
    print(json.dumps({'version':VERSION,'files':len(manifest),'rebuilt_and_snapshots':len(rows),'source_snapshot_current':True}),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reuse-source-archive',action='store_true');args=parser.parse_args()
    not_running();rows=verify_components()
    if not args.reuse_source_archive:sources()
    notices();runtime(rows)
if __name__=='__main__':main()
