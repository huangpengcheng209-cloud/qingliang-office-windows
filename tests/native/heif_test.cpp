// Qingliang community HEIC integration tests, 2026-10-22. No user images are read.
#include <libheif/heif.h>
#include <libde265/de265.h>
#include <x265.h>
#include <algorithm>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

static int passed = 0, failed = 0;
static void check(const char* name, bool result) {
    std::cerr << (result ? "PASS " : "FAIL ") << name << '\n';
    result ? ++passed : ++failed;
}
static void require(heif_error e, const char* operation) {
    if (e.code != heif_error_Ok) throw std::runtime_error(std::string(operation)+": "+e.message);
}
static std::vector<unsigned char> read(const std::string& file) {
    std::ifstream input(file, std::ios::binary);
    if (!input) throw std::runtime_error("Cannot read fixture: "+file);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}
static void write(const std::string& file, const std::vector<unsigned char>& data) {
    std::ofstream output(file, std::ios::binary);
    output.write(reinterpret_cast<const char*>(data.data()),data.size());
    if (!output) throw std::runtime_error("Cannot write evidence: "+file);
}
static heif_error append(heif_context*, const void* data, size_t size, void* opaque) {
    auto& bytes = *static_cast<std::vector<unsigned char>*>(opaque);
    const auto ptr = static_cast<const unsigned char*>(data);
    bytes.insert(bytes.end(),ptr,ptr+size);
    return {heif_error_Ok,heif_suberror_Unspecified,"Success"};
}
static heif_error failWrite(heif_context*, const void*, size_t, void*) {
    return {heif_error_Encoding_error,heif_suberror_Unspecified,"Injected writer failure"};
}
static std::vector<unsigned char> serialize(heif_context* ctx) {
    heif_writer writer = {1,append};
    std::vector<unsigned char> bytes;
    require(heif_context_write(ctx,&writer,&bytes),"Serialize HEIC");
    return bytes;
}
static heif_encoder* encoder(heif_context* ctx) {
    heif_encoder* result = nullptr;
    require(heif_context_get_encoder_for_format(ctx,heif_compression_HEVC,&result),"Get HEVC encoder");
    require(heif_encoder_set_lossless(result,1),"Enable lossless coding");
    require(heif_encoder_set_parameter_string(result,"preset","ultrafast"),"Set encode preset");
    require(heif_encoder_set_logging_level(result,0),"Set log level");
    return result;
}
static std::vector<unsigned char> planar(const heif_image* image) {
    std::vector<unsigned char> result;
    for (auto channel : {heif_channel_Y,heif_channel_Cb,heif_channel_Cr}) {
        int stride = 0;
        auto bytes = heif_image_get_plane_readonly(image,channel,&stride);
        const int width = heif_image_get_width(image,channel), height = heif_image_get_height(image,channel);
        if (!bytes || width <= 0 || height <= 0) throw std::runtime_error("Missing decoded plane");
        for (int y=0; y<height; ++y) result.insert(result.end(),bytes+y*stride,bytes+y*stride+width);
    }
    return result;
}
static int run(const std::string& fixtures, const std::string& source) {
    check("Pinned library versions", std::string(heif_get_version())=="1.18.2" &&
          std::string(de265_get_version())=="1.0.16" && std::string(x265_version_str).find("4.1")==0);
    check("Static HEVC encoder and decoder", heif_have_encoder_for_format(heif_compression_HEVC) &&
          heif_have_decoder_for_format(heif_compression_HEVC));
    const heif_encoder_descriptor* descriptors[4] = {};
    const int found = heif_get_encoder_descriptors(heif_compression_HEVC,"x265",descriptors,4);
    check("x265 encoder descriptor", found==1 && std::string(heif_encoder_descriptor_get_id_name(descriptors[0]))=="x265");
    auto ctx = heif_context_alloc();
    auto enc = encoder(ctx);
    constexpr int width=96,height=80;
    heif_image* input = nullptr;
    require(heif_image_create(width,height,heif_colorspace_YCbCr,heif_chroma_420,&input),"Create image");
    for (auto channel : {heif_channel_Y,heif_channel_Cb,heif_channel_Cr}) {
        const int w = channel==heif_channel_Y ? width : width/2;
        const int h = channel==heif_channel_Y ? height : height/2;
        require(heif_image_add_plane(input,channel,w,h,8),"Allocate image plane");
        int stride=0;
        auto plane=heif_image_get_plane(input,channel,&stride);
        for (int y=0;y<h;++y) for(int x=0;x<w;++x)
            plane[y*stride+x] = channel==heif_channel_Y ? (x*2+y*3)%220+16 : 100+(x/8+y/8)%50;
    }
    const auto expected=planar(input);
    write(fixtures+"/expected.yuv",expected);
    check("Synthetic YCbCr plane construction",expected.size()==width*height*3/2);
    heif_image_handle* handle = nullptr;
    require(heif_context_encode_image(ctx,input,enc,nullptr,&handle),"Encode lossless image");
    require(heif_context_set_primary_image(ctx,handle),"Set primary image");
    check("Lossless HEVC image encoding", handle && heif_image_handle_get_width(handle)==width);
    const std::vector<unsigned char> exif={'I','I',42,0,8,0,0,0,0,0,0,0,0,0};
    const std::string xmp="<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'/></x:xmpmeta>";
    require(heif_context_add_exif_metadata(ctx,handle,exif.data(),static_cast<int>(exif.size())),"Add EXIF");
    require(heif_context_add_XMP_metadata(ctx,handle,xmp.data(),static_cast<int>(xmp.size())),"Add XMP");
    heif_writer badWriter={1,failWrite};
    check("Writer failure propagation",heif_context_write(ctx,&badWriter,nullptr).code==heif_error_Encoding_error);
    heif_image_handle* thumbnail = nullptr;
    require(heif_context_encode_thumbnail(ctx,input,handle,enc,nullptr,32,&thumbnail),"Encode thumbnail");
    auto bytes=serialize(ctx);
    check("HEIC container writer",bytes.size()>100 && std::memcmp(bytes.data()+4,"ftyp",4)==0 &&
          heif_check_filetype(bytes.data(),static_cast<int>(bytes.size()))==heif_filetype_yes_supported);
    write(fixtures+"/synthetic.heic",bytes);
    auto restored=heif_context_alloc();
    require(heif_context_read_from_file(restored,(fixtures+"/synthetic.heic").c_str(),nullptr),"Read file");
    heif_image_handle* primary=nullptr;
    require(heif_context_get_primary_image_handle(restored,&primary),"Get primary handle");
    check("File primary image and dimensions",heif_image_handle_get_width(primary)==width &&
          heif_image_handle_get_height(primary)==height && heif_context_get_number_of_top_level_images(restored)==1);
    heif_image* decoded=nullptr;
    require(heif_decode_image(primary,&decoded,heif_colorspace_YCbCr,heif_chroma_420,nullptr),"Decode lossless image");
    const auto actual=planar(decoded);
    write(fixtures+"/decoded.yuv",actual);
    check("Lossless Y Cb Cr bytes",actual==expected);
    heif_item_id metadata[4]={};
    int count=heif_image_handle_get_list_of_metadata_block_IDs(primary,nullptr,metadata,4);
    bool exifOk=false,xmpOk=false;
    for (int i=0;i<count;++i) {
        std::vector<unsigned char> data(heif_image_handle_get_metadata_size(primary,metadata[i]));
        require(heif_image_handle_get_metadata(primary,metadata[i],data.data()),"Read metadata");
        const std::string type=heif_image_handle_get_metadata_type(primary,metadata[i]);
        if (type=="Exif") exifOk=data.size()>=exif.size() && std::equal(exif.rbegin(),exif.rend(),data.rbegin());
        if (type=="mime") xmpOk=std::string(data.begin(),data.end())==xmp;
    }
    check("EXIF and XMP byte preservation",count==2 && exifOk && xmpOk);
    // Alpha is a separate HEVC auxiliary image, tested independently of RGB conversion precision.
    auto actx=heif_context_alloc(); auto aenc=encoder(actx);
    heif_image* rgba=nullptr;
    require(heif_image_create(64,48,heif_colorspace_RGB,heif_chroma_interleaved_RGBA,&rgba),"Create RGBA");
    require(heif_image_add_plane(rgba,heif_channel_interleaved,64,48,8),"Allocate RGBA");
    int stride=0; auto pixels=heif_image_get_plane(rgba,heif_channel_interleaved,&stride);
    for (int y=0;y<48;++y) for(int x=0;x<64;++x) {
        auto p=pixels+y*stride+x*4;p[0]=p[1]=p[2]=128;p[3]=(x*4+y)%256;
    }
    heif_image_handle* ah=nullptr;
    require(heif_context_encode_image(actx,rgba,aenc,nullptr,&ah),"Encode RGBA");
    auto ab=serialize(actx);write(fixtures+"/alpha.heic",ab);
    auto aread=heif_context_alloc();
    require(heif_context_read_from_memory_without_copy(aread,ab.data(),ab.size(),nullptr),"Read alpha HEIC");
    heif_image_handle* arh=nullptr;heif_image* ad=nullptr;
    require(heif_context_get_primary_image_handle(aread,&arh),"Get alpha handle");
    require(heif_decode_image(arh,&ad,heif_colorspace_RGB,heif_chroma_interleaved_RGBA,nullptr),"Decode RGBA");
    auto ap=heif_image_get_plane_readonly(ad,heif_channel_interleaved,&stride);
    bool alpha=ap && heif_image_handle_has_alpha_channel(arh);
    for(int y=0;y<48 && alpha;++y) for(int x=0;x<64;++x) alpha=alpha && ap[y*stride+x*4+3]==(x*4+y)%256;
    check("Memory container and lossless alpha",alpha);
    heif_item_id thumbId=0;heif_image_handle* th=nullptr;heif_image* td=nullptr;
    bool thumb=heif_image_handle_get_number_of_thumbnails(primary)==1 && heif_image_handle_get_list_of_thumbnail_IDs(primary,&thumbId,1)==1;
    if(thumb) {
        require(heif_image_handle_get_thumbnail(primary,thumbId,&th),"Get thumbnail");
        require(heif_decode_image(th,&td,heif_colorspace_RGB,heif_chroma_interleaved_RGB,nullptr),"Decode thumbnail");
        thumb=heif_image_handle_get_width(th)>0 && heif_image_handle_get_width(th)<=32 && heif_image_handle_get_height(th)<=32;
    }
    check("Attached thumbnail decode and bounds",thumb);
    auto external=heif_context_alloc();
    require(heif_context_read_from_file(external,(source+"/examples/example.heic").c_str(),nullptr),"Read upstream HEIC");
    heif_image_handle* eh=nullptr;heif_image* ed=nullptr;
    require(heif_context_get_primary_image_handle(external,&eh),"Get external primary");
    require(heif_decode_image(eh,&ed,heif_colorspace_RGB,heif_chroma_interleaved_RGB,nullptr),"Decode upstream HEIC");
    check("Upstream 1280x854 HEIC fixture",heif_image_handle_get_width(eh)==1280 && heif_image_handle_get_height(eh)==854 &&
          heif_image_get_width(ed,heif_channel_interleaved)==1280);
    auto bad=heif_context_alloc();
    check("Truncated container rejected",heif_context_read_from_memory_without_copy(bad,bytes.data(),12,nullptr).code!=heif_error_Ok);
    heif_context_free(bad);bad=heif_context_alloc();
    auto corrupt=bytes;corrupt[0]=corrupt[1]=corrupt[2]=0;corrupt[3]=2;
    check("Invalid box size rejected",heif_context_read_from_memory_without_copy(bad,corrupt.data(),corrupt.size(),nullptr).code!=heif_error_Ok);
    heif_context_free(bad);
    auto avif=heif_context_alloc();heif_image_handle* avh=nullptr;heif_image* avd=nullptr;
    require(heif_context_read_from_file(avif,(source+"/examples/example.avif").c_str(),nullptr),"Read AVIF metadata");
    require(heif_context_get_primary_image_handle(avif,&avh),"Get AVIF handle");
    const auto unavailable=heif_decode_image(avh,&avd,heif_colorspace_RGB,heif_chroma_interleaved_RGB,nullptr);
    check("Upstream profile reports unavailable AV1 decoder",!heif_have_decoder_for_format(heif_compression_AV1) && unavailable.code!=heif_error_Ok);
    if(avd)heif_image_release(avd);heif_image_handle_release(avh);heif_context_free(avif);
    heif_image_release(ed);heif_image_handle_release(eh);heif_context_free(external);
    if(td)heif_image_release(td);if(th)heif_image_handle_release(th);
    heif_image_release(ad);heif_image_handle_release(arh);heif_context_free(aread);
    heif_image_handle_release(ah);heif_image_release(rgba);heif_encoder_release(aenc);heif_context_free(actx);
    heif_image_release(decoded);heif_image_handle_release(primary);heif_context_free(restored);
    if(thumbnail)heif_image_handle_release(thumbnail);heif_image_handle_release(handle);heif_image_release(input);
    heif_encoder_release(enc);heif_context_free(ctx);
    std::cout<<"{\"passed\":"<<passed<<",\"failed\":"<<failed<<"}\n";
    return failed?1:0;
}
int main(int argc,char** argv) {
    try { if(argc!=3)throw std::runtime_error("Expected fixture output and pinned libheif source paths");return run(argv[1],argv[2]); }
    catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 2;}
}
