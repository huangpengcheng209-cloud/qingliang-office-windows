// Qingliang community graphics DLL integration tests, 2026-10-22.
#include <windows.h>
#include <DesktopEditor/graphics/pro/Graphics.h>
#include <DesktopEditor/graphics/pro/Fonts.h>
#include <DesktopEditor/raster/BgraFrame.h>
#include <DesktopEditor/raster/ImageFileFormatChecker.h>
#define SUPPORT_HARFBUZZ_SHAPER
#include <DesktopEditor/fontengine/TextShaper.h>
#include <DesktopEditor/fontengine/TextHyphen.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <vector>

static int passed=0,failed=0;
static void check(const char* name,bool ok){std::cerr<<(ok?"PASS ":"FAIL ")<<name<<'\n';ok?++passed:++failed;}
static void frame(CBgraFrame& f,int w,int h){
    f.put_Width(w);f.put_Height(h);f.put_Stride(4*w);
    auto p=new BYTE[static_cast<size_t>(w)*h*4];std::memset(p,255,static_cast<size_t>(w)*h*4);f.put_Data(p);
}
static BYTE* pixel(CBgraFrame& f,int x,int y){
    const int row=f.get_Stride()<0 ? f.get_Height()-1-y : y;
    return f.get_Data()+4*(row*f.get_Width()+x);
}
static bool color(CBgraFrame& f,int x,int y,int r,int g,int b,int tolerance=2){
    auto p=pixel(f,x,y);return std::abs(p[2]-r)<=tolerance&&std::abs(p[1]-g)<=tolerance&&std::abs(p[0]-b)<=tolerance;
}
static NSGraphics::IGraphicsRenderer* renderer(CBgraFrame& f){
    auto r=NSGraphics::Create();if(!r)throw std::runtime_error("Graphics factory failed");
    r->CreateFromBgraFrame(&f);r->put_Width(f.get_Width());r->put_Height(f.get_Height());
    r->put_BrushType(1000);r->put_BrushAlpha1(255);return r;
}
static void rect(NSGraphics::IGraphicsRenderer* r,int color,double x,double y,double w,double h){
    r->put_BrushColor1(color);r->PathCommandStart();r->PathCommandRect(x,y,w,h);r->Fill();r->PathCommandEnd();
}
static size_t dark(CBgraFrame& f,int top,int bottom){
    size_t n=0;for(int y=top;y<bottom;++y)for(int x=0;x<f.get_Width();++x){auto p=pixel(f,x,y);if(p[0]<200||p[1]<200||p[2]<200)++n;}return n;
}
static bool same(CBgraFrame& a,CBgraFrame& b){
    if(a.get_Width()!=b.get_Width()||a.get_Height()!=b.get_Height())return false;
    for(int y=0;y<a.get_Height();++y)if(std::memcmp(pixel(a,0,y),pixel(b,0,y),a.get_Width()*4)!=0)return false;
    return true;
}
static unsigned u32(const BYTE* p){unsigned value;std::memcpy(&value,p,4);return value;}
static int i32(const BYTE* p){int value;std::memcpy(&value,p,4);return value;}
static int run(const std::filesystem::path& out,const std::filesystem::path& source,const std::filesystem::path& heifFixtures){
    CBgraFrame drawing;frame(drawing,256,192);auto r=renderer(drawing);
    check("Graphics factory and BGRA target",drawing.get_Data()&&r);
    rect(r,0xff0000,20,20,80,50);
    check("Solid rectangle interior",color(drawing,40,40,255,0,0));
    check("Rectangle exterior remains white",color(drawing,5,5,255,255,255));
    r->put_PenColor(0);r->put_PenAlpha(255);r->put_PenSize(3);
    r->PathCommandStart();r->PathCommandMoveTo(10,100);r->PathCommandLineTo(120,100);r->Stroke();r->PathCommandEnd();
    check("Vector stroke",color(drawing,60,100,0,0,0,15));
    r->put_BrushAlpha1(128);rect(r,0xff0000,150,20,50,50);r->put_BrushAlpha1(255);
    check("Alpha compositing",color(drawing,170,40,255,127,127,3));
    r->SetTransform(1,0,0,1,40,20);rect(r,0x0000ff,20,120,30,20);r->SetTransform(1,0,0,1,0,0);
    check("Affine transform",color(drawing,70,150,0,0,255));
    r->put_BrushColor1(0x00ff00);r->PathCommandStart();r->PathCommandRect(150,100,80,70);r->PathCommandRect(170,120,20,20);r->DrawPath(c_nEvenOddFillMode);r->PathCommandEnd();
    check("Even odd path hole",color(drawing,160,110,0,255,0)&&color(drawing,180,130,255,255,255));
    r->Release();
    auto png=out/L"绘图-\U0001f600.png";
    bool saved=drawing.SaveFile(png.wstring(),_CXIMAGE_FORMAT_PNG);
    CBgraFrame decoded;
    check("PNG Unicode path and exact pixels",saved&&decoded.OpenFile(png.wstring())&&same(drawing,decoded));
    auto jpeg=out/L"drawing.jpg";drawing.SetJpegQuality(95);
    bool jpg=drawing.SaveFile(jpeg.wstring(),_CXIMAGE_FORMAT_JPG);CBgraFrame jd;
    if(jpg)jpg=jd.OpenFile(jpeg.wstring())&&jd.get_Width()==256&&jd.get_Height()==192;
    double error=0;if(jpg){for(int y=0;y<192;++y)for(int x=0;x<256;++x)for(int c=0;c<3;++c)error+=std::abs(pixel(drawing,x,y)[c]-pixel(jd,x,y)[c]);error/=256*192*3;}
    check("JPEG dimensions and bounded pixel error",jpg&&error<12);
    auto bmp=out/L"drawing.bmp";CBgraFrame bd;
    check("BMP exact opaque pixels",drawing.SaveFile(bmp.wstring(),_CXIMAGE_FORMAT_BMP)&&bd.OpenFile(bmp.wstring())&&same(drawing,bd));
    check("Resize dimensions and corner color",decoded.Resize(64,48)&&decoded.get_Width()==64&&decoded.get_Height()==48&&color(decoded,0,0,255,255,255));
    BYTE* encoded=nullptr;int length=0;CBgraFrame memory;
    bool mem=drawing.Encode(encoded,length,_CXIMAGE_FORMAT_PNG)&&length>100&&memory.Decode(encoded,length,_CXIMAGE_FORMAT_PNG)&&same(drawing,memory);
    if(encoded)CBgraFrame::FreeEncodedMemory(encoded);
    check("PNG memory encode and decode",mem);
    BYTE invalid[]={1,2,3,4,5,6,7,8};CBgraFrame bad;
    check("Malformed image rejected",!bad.Decode(invalid,sizeof(invalid)));
    CImageFileFormatChecker format(png.wstring());
    check("Image format detection",format.eFileType==_CXIMAGE_FORMAT_PNG);
    CBgraFrame heic;
    check("HEIC imported through graphics DLL",heic.OpenFile((source/L"Common/3dParty/heif/libheif/examples/example.heic").wstring())&&heic.get_Width()==1280&&heic.get_Height()==854);
    CBgraFrame alpha;
    bool a=alpha.OpenFile((heifFixtures/L"alpha.heic").wstring())&&alpha.get_Width()==64&&alpha.get_Height()==48;
    if(a)for(int y=0;y<48;++y)for(int x=0;x<64;++x)a=a&&pixel(alpha,x,y)[3]==(x*4+y)%256;
    check("HEIC auxiliary alpha preserved",a);
    auto fonts=NSFonts::NSApplication::Create();
    const auto fontDir=source/L"Common/3dParty/harfbuzz/harfbuzz/perf/fonts";
    auto latin=(fontDir/L"Roboto-Regular.ttf").wstring(),arabic=(fontDir/L"Amiri-Regular.ttf").wstring();
    std::vector<std::wstring> files={latin,arabic};fonts->InitializeFromArrayFiles(files,0);
    auto manager=fonts->GenerateFontManager();
    CBgraFrame text;frame(text,640,200);auto tr=renderer(text);tr->SetFontManager(manager);
    constexpr double mm=25.4/96.0;
    tr->put_Width(640*mm);tr->put_Height(200*mm);
    bool loaded=manager->LoadFontFromFile(latin,0,32,96,96)!=0;
    tr->put_FontPath(latin);tr->put_FontSize(32);tr->put_FontStyle(0);tr->put_BrushColor1(0);tr->CommandDrawText(L"Office ffi - Qingliang",20*mm,60*mm,600*mm,45*mm);
    check("Pinned Latin font and text raster",loaded&&dark(text,0,95)>150);
    std::ifstream af(std::filesystem::path(arabic),std::ios::binary);
    std::vector<BYTE> fontBytes{std::istreambuf_iterator<char>(af),{}};
    auto library=NSShaper::FT_Library_Init();
    auto face=NSShaper::FT_Open_Face(library,fontBytes.data(),static_cast<unsigned>(fontBytes.size()),0);
    if(!face)throw std::runtime_error("Cannot open pinned Arabic shaping face");
    NSShaper::FT_Set_Char_Size(face,0,32*64,96,96);
    void* hbFont=nullptr;NSShaper::CExternalPointer shaped;
    NSShaper::HB_ShapeText(face,hbFont,std::string(u8"السلام عليكم"),1,0x41726162,5,NSShaper::HB_LanguageFromString("ar"),&shaped);
    bool rtl=shaped.Len>=12&&(shaped.Len-12)%26==0;unsigned previous=~0u;
    tr->put_FontPath(arabic);double pen=20;
    for(unsigned at=12;at+26<=shaped.Len;at+=26){
        auto p=shaped.Data+at;unsigned gid=u32(p+2),cluster=u32(p+6);
        rtl=rtl&&gid&&cluster<=previous;previous=cluster;
        tr->CommandDrawTextExCHAR(0,gid,(pen+i32(p+18)/64.0)*mm,(145-i32(p+22)/64.0)*mm,0,0);
        pen+=i32(p+10)/64.0;
    }
    check("Graphics HarfBuzz RTL bridge and Arabic raster",rtl&&dark(text,100,200)>100);
    NSShaper::HB_FontFree(hbFont);NSShaper::FT_Done_Face(face);NSShaper::FT_Library_Destroy(library);
    tr->Release();text.SaveFile((out/L"text.png").wstring(),_CXIMAGE_FORMAT_PNG);manager->Release();
    CBgraFrame svg;frame(svg,100,100);auto sr=renderer(svg);auto meta=MetaFile::Create(fonts);
    std::string xml="<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><style>rect { fill: #00ff00; }</style><rect x='10' y='10' width='80' height='80'/></svg>";
    bool vector=meta->LoadFromBuffer(reinterpret_cast<BYTE*>(xml.data()),static_cast<unsigned>(xml.size()));
    if(vector)vector=meta->DrawOnRenderer(sr,0,0,100,100);
    check("SVG CSS parsing and raster",vector&&color(svg,50,50,0,255,0));
    meta->Release();sr->Release();svg.SaveFile((out/L"svg.png").wstring(),_CXIMAGE_FORMAT_PNG);
    auto emf=out/L"vector.emf";RECT bounds={0,0,10000,10000};auto dc=CreateEnhMetaFileW(nullptr,emf.c_str(),&bounds,L"Qingliang\0integration-test\0\0");
    bool emfOk=dc!=nullptr;
    if(dc){RECT box={10,10,90,90};auto brush=CreateSolidBrush(RGB(0,0,255));FillRect(dc,&box,brush);DeleteObject(brush);auto handle=CloseEnhMetaFile(dc);emfOk=handle!=nullptr;if(handle)DeleteEnhMetaFile(handle);}
    CBgraFrame emfRaster;frame(emfRaster,100,100);auto er=renderer(emfRaster);er->SetSwapRGB(false);auto em=MetaFile::Create(fonts);
    emfOk=emfOk&&em->LoadFromFile(emf.c_str())&&em->DrawOnRenderer(er,0,0,100,100);
    check("Windows EMF blue pixels and white background",emfOk&&color(emfRaster,10,10,0,0,255)&&color(emfRaster,80,80,255,255,255));
    em->Release();er->Release();emfRaster.SaveFile((out/L"emf.png").wstring(),_CXIMAGE_FORMAT_PNG);fonts->Release();
    NSHyphen::CEngine hyphen;
    const std::string dictionary="UTF-8\nLEFTHYPHENMIN 1\nRIGHTHYPHENMIN 1\na1b\n";
    bool dict=hyphen.LoadDictionary(1033,reinterpret_cast<const BYTE*>(dictionary.data()),static_cast<unsigned>(dictionary.size()))==0;
    auto positions=dict?hyphen.Process(1033,"abcd",4):nullptr;
    check("Pinned Hyphen dictionary and word break",positions&&(positions[0]&1));
    std::cout<<"{\"passed\":"<<passed<<",\"failed\":"<<failed<<"}\n";
    return failed?1:0;
}
int wmain(int argc,wchar_t** argv){try{if(argc!=4)throw std::runtime_error("Expected output, source, and HEIF fixture directories");return run(argv[1],argv[2],argv[3]);}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
