from pathlib import Path
root=Path(r'D:\CodexCache\office-windows\upstream\DesktopEditors\sdkjs')
path=root/'pdf/src/document.js';raw=path.read_bytes();nl=b'\r\n' if b'\r\n' in raw else b'\n';text=raw.decode('utf-8').replace('\r\n','\n')
start=text.index('    function normalizeScannedPdfBaseFonts(');end=text.index('    CPDFDoc.prototype.EditPage',start)
text=text[:start]+text[end:];text=text.replace('new AscCommon.StaxParser(normalizeScannedPdfBaseFonts(aSpsXmls[i]), undefined, oParserContext)','new AscCommon.StaxParser(aSpsXmls[i], undefined, oParserContext)')
path.write_bytes(text.replace('\n',nl.decode()).encode('utf-8'))
path=root/'common/Shapes/Serialize.js';raw=path.read_bytes();nl=b'\r\n' if b'\r\n' in raw else b'\n';text=raw.decode('utf-8').replace('\r\n','\n')
marker='var c_dScalePPTXSizes = 36000;';assert 'getPdfBaseFontFallback' not in text
helper='''
function getPdfBaseFontFallback(name, selectedFamily)
{
    // Original PDF base-font names survive binary scanning. Use their
    // installed metric-compatible family for newly typed characters while
    // retaining the original embedded font and glyph IDs for existing text.
    var family;
    if (/^Helvetica(?:-Bold|-Oblique|-BoldOblique)?$/.test(name))
        family = "Arial";
    else if (/^Times-(?:Roman|Bold|Italic|BoldItalic)$/.test(name))
        family = "Times New Roman";
    else if (/^Courier(?:-Bold|-Oblique|-BoldOblique)?$/.test(name))
        family = "Courier New";
    if (family && AscFonts.g_fontApplication.GetFontInfoName(family) === family)
        return family;
    return selectedFamily;
}
'''
text=text.replace(marker,marker+'\n'+helper,1)
old='Asc.editor.embeddedFontsMap[AscFonts.getEmbeddedFontPrefix() + oPdfFontInfo.name] = _run.GetFontFamily();';assert text.count(old)==1
text=text.replace(old,'Asc.editor.embeddedFontsMap[AscFonts.getEmbeddedFontPrefix() + oPdfFontInfo.name] = getPdfBaseFontFallback(oPdfFontInfo.name, _run.GetFontFamily());')
path.write_bytes(text.replace('\n',nl.decode()).encode('utf-8'));print('Prepared binary PDF embedded-font fallback; removed inactive XML-only attempt.')
