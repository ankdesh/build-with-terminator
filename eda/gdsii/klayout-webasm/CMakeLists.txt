cmake_minimum_required(VERSION 3.15)
project(klayout_wasm CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Definitions required by KLayout core without Qt, Python, or Ruby
add_definitions(
    -DHAVE_64BIT_COORD=1
    -DHAVE_ZLIB=1
    -DMAKE_TL_LIBRARY
    -DMAKE_GSI_LIBRARY
    -DMAKE_DB_LIBRARY
    -D__linux__
)

set(KLAYOUT_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/klayout/src)

include_directories(
    ${KLAYOUT_SRC_DIR}/tl/tl
    ${KLAYOUT_SRC_DIR}/gsi/gsi
    ${KLAYOUT_SRC_DIR}/db/db
    ${KLAYOUT_SRC_DIR}/version
    ${CMAKE_CURRENT_SOURCE_DIR}/bindings
)

# Source files for klayout_tl
file(GLOB TL_SOURCES
    "${KLAYOUT_SRC_DIR}/tl/tl/*.cc"
)

# Exclude Qt, Curl, Git, and Windows specific files from TL
list(FILTER TL_SOURCES EXCLUDE REGEX ".*Qt\\.cc$")
list(FILTER TL_SOURCES EXCLUDE REGEX ".*Curl\\.cc$")
list(FILTER TL_SOURCES EXCLUDE REGEX ".*Git\\.cc$")
list(FILTER TL_SOURCES EXCLUDE REGEX ".*FileSystemWatcher\\.cc$")
list(FILTER TL_SOURCES EXCLUDE REGEX ".*WebDAV\\.cc$")

# Source files for klayout_gsi
file(GLOB GSI_SOURCES
    "${KLAYOUT_SRC_DIR}/gsi/gsi/*.cc"
)
list(FILTER GSI_SOURCES EXCLUDE REGEX ".*gsiExternalMain\\.cc$")

# Source files for klayout_db
file(GLOB DB_SOURCES
    "${KLAYOUT_SRC_DIR}/db/db/*.cc"
)

# Exclude GSI binding generated declarations (used for Ruby/Python GSI generation)
list(FILTER DB_SOURCES EXCLUDE REGEX ".*gsiDecl.*\\.cc$")

# Combine source files
set(ALL_SOURCES
    ${TL_SOURCES}
    ${GSI_SOURCES}
    ${DB_SOURCES}
    bindings/klayout_bind.cc
)

add_executable(klayout_db ${ALL_SOURCES})

# Emscripten target flags
set_target_properties(klayout_db PROPERTIES
    OUTPUT_NAME "klayout_db"
    SUFFIX ".js"
)

target_compile_options(klayout_db PUBLIC
    -O3
    -fexceptions
    -sUSE_ZLIB=1
    -Wno-deprecated-declarations
)

target_link_options(klayout_db PUBLIC
    --bind
    -O3
    -fexceptions
    -sUSE_ZLIB=1
    -sALLOW_MEMORY_GROWTH=1
    -sMAXIMUM_MEMORY=4GB
    -sMODULARIZE=1
    -sEXPORT_NAME="createKLayoutModule"
    -sEXPORTED_RUNTIME_METHODS=['FS','MEMFS']
    -sFORCE_FILESYSTEM=1
)
