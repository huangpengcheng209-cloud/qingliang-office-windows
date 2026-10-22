// Qingliang community: native text and VBA parser checks, 2026-10-22.
#include <windows.h>
#include <objbase.h>
#include <MsBinaryFile/Common/Vba/VbaBinary.h>
#include <TxtFile/Source/TxtFormat/TxtFile.h>
#include <UnicodeConverter/UnicodeConverter_Encodings.h>
#include <algorithm>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>

using Bytes=std::vector<unsigned char>;
static void write(const std::filesystem::path& path,const Bytes& data){std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(data.data()),data.size());if(!f)throw std::runtime_error("fixture write failed");}
static Bytes bytes(const std::string& s){return Bytes(s.begin(),s.end());}
static Bytes read(const std::filesystem::path& path){std::ifstream f(path,std::ios::binary);return Bytes(std::istreambuf_iterator<char>(f),{});}
static Bytes utf16(const std::wstring& text,bool be){Bytes b=be?Bytes{0xfe,0xff}:Bytes{0xff,0xfe};for(auto c:text){b.push_back(be?(c>>8)&255:c&255);b.push_back(be?c&255:(c>>8)&255);}return b;}
static Bytes chunk(const Bytes& payload,bool compressed=true){unsigned h=(compressed?0xb000:0x3000)|static_cast<unsigned>(payload.size()-1);Bytes b{1,static_cast<unsigned char>(h),static_cast<unsigned char>(h>>8)};b.insert(b.end(),payload.begin(),payload.end());return b;}
static Bytes literal(const std::string& s){Bytes p;for(size_t i=0;i<s.size();i+=8){p.push_back(0);p.insert(p.end(),s.begin()+i,s.begin()+std::min(i+8,s.size()));}return chunk(p);}
static void ole(const std::filesystem::path& path,const Bytes& data){IStorage* storage=nullptr;HRESULT hr=StgCreateDocfile(path.c_str(),STGM_CREATE|STGM_READWRITE|STGM_SHARE_EXCLUSIVE,0,&storage);if(FAILED(hr))throw std::runtime_error("OLE create failed");IStream* stream=nullptr;hr=storage->CreateStream(L"Data",STGM_CREATE|STGM_READWRITE|STGM_SHARE_EXCLUSIVE,0,0,&stream);if(FAILED(hr)){storage->Release();throw std::runtime_error("OLE stream failed");}ULONG written=0;hr=stream->Write(data.data(),static_cast<ULONG>(data.size()),&written);stream->Release();storage->Commit(STGC_DEFAULT);storage->Release();if(FAILED(hr)||written!=data.size())throw std::runtime_error("OLE write failed");}
struct VbaFixture{
    POLE::Storage storage;std::unique_ptr<POLE::Stream> stream;std::unique_ptr<CVbaFileStream> parser;
    VbaFixture(const std::filesystem::path& path,const Bytes& data,unsigned offset=0):storage(path.c_str()){
        ole(path,data);if(!storage.open())throw std::runtime_error("POLE open failed");stream.reset(new POLE::Stream(&storage,L"/Data"));parser.reset(new CVbaFileStream(stream.get(),offset));
    }
    Bytes decoded(){auto p=parser->getData();return parser->getDataSize()?Bytes(p,p+parser->getDataSize()):Bytes{};}
};
static bool run(int id,const std::filesystem::path& out){
    auto path=out/L"input.txt";const std::wstring text=L"\u4e2d\u6587\U0001f600";
    const std::string utf8=u8"\u4e2d\u6587\U0001f600";
    if(id==0){auto b=bytes("\xef\xbb\xbf"+utf8+"\r\nsecond\nthird\r");write(path,b);TxtFile f(path);return f.readUnicodeLines(-1)==std::vector<std::wstring>{text,L"second",L"third"}&&f.getLinesCount()==3;}
    if(id==1){write(path,bytes(utf8+"\nlast"));TxtFile f(path);return f.readUtf8Lines(-1)==std::vector<std::string>{utf8,"last"};}
    if(id==2||id==3){write(path,utf16(text+L"\r\nlast",id==3));TxtFile f(path);return f.readUnicodeLines(-1)==std::vector<std::wstring>{text,L"last"};}
    if(id==4){int index=-1;for(int i=0;i<UNICODE_CONVERTER_ENCODINGS_COUNT;++i)if(std::string(NSUnicodeConverter::Encodings[i].Name)=="GBK")index=i;if(index<0)throw std::runtime_error("Pinned GBK encoding absent");write(path,Bytes{0xd6,0xd0,0xce,0xc4});TxtFile f(path);return f.readUnicodeLines(index)==std::vector<std::wstring>{L"\u4e2d\u6587"};}
    if(id==5){write(path,bytes("\xef\xbb\xbf\r\n\nend"));TxtFile f(path);return f.readUnicodeLines(-1)==std::vector<std::wstring>{L"",L"",L"end"};}
    if(id==6){write(path,bytes("a\nb"));TxtFile f(path);f.readUtf8Lines(-1);f.readUtf8Lines(-1);return f.getLinesCount()==2;}
    if(id==7){write(path,bytes("a\nb"));TxtFile f(path);f.readUtf8Lines(-1);write(path,{});return f.readUtf8Lines(-1).empty()&&f.getLinesCount()==0;}
    if(id==8){TxtFile f(path);return f.readUnicodeLines(-1).empty()&&f.getLinesCount()==0;}
    if(id==9){const std::vector<std::wstring> input={text,L"second"};const auto expected=input;TxtFile f(path);return f.writeBigEndian(input)&&input==expected;}
    if(id==10){std::vector<std::wstring> input={text,L"second"};TxtFile f(path);return f.writeBigEndian(input)&&read(path)==utf16(text+L"\r\nsecond\r\n",true)&&f.readUnicodeLines(-1)==std::vector<std::wstring>{text,L"second"};}
    if(id==11){std::vector<std::wstring> input={text,L"second"};TxtFile f(path);return f.writeUnicode(input)&&read(path)==utf16(text+L"\r\nsecond\r\n",false)&&f.readUnicodeLines(-1)==input;}
    if(id==12){TxtFile f(path);return f.writeUtf8({utf8,"second"})&&read(path)==bytes("\xef\xbb\xbf"+utf8+"\r\nsecond");}
    if(id==13){path=out/L"\u6587\u672c-\U0001f600.txt";TxtFile f(path);return f.writeUtf8({utf8})&&f.readUtf8Lines(-1)==std::vector<std::string>{utf8};}
    if(id==14){TxtFile f(out/L"missing/invalid.txt");return !f.writeUtf8({"a"});}
    if(id==15){write(path,Bytes{0xef,0xbb,0xbf});TxtFile f(path);return f.readUnicodeLines(-1).empty()&&f.getLinesCount()==0;}
    path=out/L"project.ole";
    if(id==16){VbaFixture f(path,bytes("PROJECT\r\n"));return f.decoded()==bytes("PROJECT\r\n");}
    if(id==17){VbaFixture f(path,literal("hello"));return f.decoded()==bytes("hello");}
    if(id==18){VbaFixture f(path,chunk(Bytes{2,'A',5,0}));return f.decoded()==bytes("AAAAAAAAA");}
    if(id==19){Bytes raw(4096);for(size_t i=0;i<raw.size();++i)raw[i]=static_cast<unsigned char>(i);VbaFixture f(path,chunk(raw,false));return f.decoded()==raw;}
    if(id==20){auto first=literal("one"),second=literal("two");first.insert(first.end(),second.begin()+1,second.end());VbaFixture f(path,first);return f.decoded()==bytes("onetwo");}
    if(id==21){auto b=literal("offset");b.insert(b.begin(),{0x42,0x43});VbaFixture f(path,b,2);return f.decoded()==bytes("offset");}
    if(id>=22&&id<=27){VbaFixture f(path,bytes("abcdefghijklmnop"));auto& p=*f.parser;
        if(id==22){p.Seek(12);unsigned value=0;return p.loadAnyData(value)&&value==0x706f6e6d&&p.GetDataPos()==16;}
        if(id==23){p.Seek(2);p.RollBack(8);return p.GetDataPos()==0;}
        if(id==24){p.Seek(999);return p.GetDataPos()==16;}
        if(id==25){p.Seek(1);p.skipBytes(std::numeric_limits<size_t>::max());return p.GetDataPos()==16;}
        if(id==26){p.Seek(1);p.Align(8);return p.GetDataPos()==8;}
        p.Align(0);return p.GetDataPos()==0;
    }
    if(id==28){VbaFixture f(path,Bytes{1,0});return f.decoded().empty();}
    if(id==29){VbaFixture f(path,Bytes{1,0xff,0x3f,'A'});return f.decoded().empty();}
    if(id==30){VbaFixture f(path,chunk(Bytes{1,0,0}));return f.decoded().empty();}
    if(id==31){CVbaFile missing(out/L"missing.ole");return missing.isError()&&!missing.getNamedStream(L"VBA/dir");}
    if(id==32){Bytes payload{0,'a','b','c','d','e','f','g','h',0,'i','j','k','l','m','n','o','p',2,'q',0,0x80};VbaFixture f(path,chunk(payload));return f.decoded()==bytes("abcdefghijklmnopqabc");}
    if(id==33){VbaFixture f(path,chunk(Bytes{2,'A',0xff,0x0f}));return f.decoded().empty();}
    if(id==34){VbaFixture f(path,literal("small"),999);return f.decoded().empty();}
    if(id==35){VbaFixture f(path,bytes("abcde"));f.parser->Seek(3);char buffer[4]={};f.parser->read(buffer,sizeof(buffer));return buffer[0]=='d'&&buffer[1]=='e'&&!buffer[2]&&!buffer[3]&&f.parser->GetDataPos()==5;}
    throw std::runtime_error("unknown case");
}
int wmain(int argc,wchar_t** argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);CoInitializeEx(nullptr,COINIT_MULTITHREADED);try{if(argc!=3)throw std::runtime_error("Expected case and output directory");bool ok=run(std::stoi(argv[1]),argv[2]);std::cout<<(ok?"PASS":"FAIL")<<'\n';CoUninitialize();return ok?0:1;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';CoUninitialize();return 2;}}
