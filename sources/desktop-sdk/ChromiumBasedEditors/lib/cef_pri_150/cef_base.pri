# Modern Windows CEF SDK selected explicitly by the Windows rebuild.
CEF_SRC_PATH = $$(OFFICE_CEF_SDK_ROOT)
isEmpty(CEF_SRC_PATH):error(OFFICE_CEF_SDK_ROOT must identify the verified CEF 150 SDK)
!exists($$CEF_SRC_PATH/include/cef_api_versions.h):error(CEF 150 generated API headers are missing)
INCLUDEPATH += $$CEF_SRC_PATH
CONFIG -= c++17
CONFIG += c++2a
QMAKE_CXXFLAGS -= /std:c++17
QMAKE_CXXFLAGS_CXX2A = /std:c++20
QMAKE_CXXFLAGS += /FI$$PWD/../src/cefwrapper/cef150_compat_types.h
DEFINES += __STD_C USING_CEF_SHARED NDEBUG WRAPPING_CEF_SHARED NO_CSR NOMINMAX _WINDOWS
# The pinned Boost 1.72 formatter uses allocator's former optional hint.
# MSVC provides this compatibility switch without changing allocation behavior.
DEFINES += _HAS_DEPRECATED_ALLOCATOR_MEMBERS=1
include($$PWD/cef_sources.pri)
LIBS += $$CEF_SRC_PATH/Release/libcef.lib
LIBS += -ld3d11 -ld3dcompiler -lglu32 -lgdi32
LIBS += -lwininet -ldnsapi -lversion -lmsimg32 -lws2_32 -lusp10 -lpsapi -lshlwapi -lwinmm -lole32 -loleaut32 -luuid -ladvapi32 -lshell32 -lcomdlg32 -lodbc32 -lodbccp32 -ldelayimp -lcredui -lnetapi32 -lcomctl32 -lrpcrt4 -lgdiplus -lUrlmon -lOpenGL32 -lCrypt32 -lImm32
