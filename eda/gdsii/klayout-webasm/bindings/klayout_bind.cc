#include <emscripten/bind.h>
#include <emscripten/val.h>
#include "dbBox.h"
#include "dbPoint.h"
#include "dbPolygon.h"
#include "dbPath.h"
#include "dbText.h"
#include "dbEdge.h"
#include "dbTrans.h"
#include "dbLayout.h"
#include "dbCell.h"
#include "dbRegion.h"
#include "dbEdges.h"
#include "dbLayerProperties.h"
#include "dbSaveLayoutOptions.h"
#include "dbLoadLayoutOptions.h"
#include "dbReader.h"
#include "dbWriter.h"
#include "tlStream.h"
#include <iostream>
#include <vector>
#include <string>

using namespace emscripten;

// Helper function to read a layout file from VFS/MEMFS
bool load_layout_file(db::Layout &layout, const std::string &filename) {
    try {
        tl::InputStream stream(filename);
        db::LoadLayoutOptions options;
        db::Reader reader(stream);
        reader.read(layout, options);
        return true;
    } catch (const std::exception &e) {
        std::cerr << "Error loading layout: " << e.what() << std::endl;
        return false;
    } catch (...) {
        std::cerr << "Unknown error loading layout file" << std::endl;
        return false;
    }
}

// Helper function to save a layout file to VFS/MEMFS
bool save_layout_file(db::Layout &layout, const std::string &filename) {
    try {
        tl::OutputStream stream(filename);
        db::SaveLayoutOptions options;
        db::Writer writer(options);
        writer.write(layout, stream);
        return true;
    } catch (const std::exception &e) {
        std::cerr << "Error saving layout: " << e.what() << std::endl;
        return false;
    } catch (...) {
        std::cerr << "Unknown error saving layout file" << std::endl;
        return false;
    }
}

EMSCRIPTEN_BINDINGS(klayout_module) {
    // db::Point
    class_<db::Point>("Point")
        .constructor<>()
        .constructor<int, int>()
        .property("x", &db::Point::x, &db::Point::set_x)
        .property("y", &db::Point::y, &db::Point::set_y);

    // db::DPoint
    class_<db::DPoint>("DPoint")
        .constructor<>()
        .constructor<double, double>()
        .property("x", &db::DPoint::x, &db::DPoint::set_x)
        .property("y", &db::DPoint::y, &db::DPoint::set_y);

    // db::Box
    class_<db::Box>("Box")
        .constructor<>()
        .constructor<int, int, int, int>()
        .constructor<const db::Point&, const db::Point&>()
        .function("left", &db::Box::left)
        .function("bottom", &db::Box::bottom)
        .function("right", &db::Box::right)
        .function("top", &db::Box::top)
        .function("width", &db::Box::width)
        .function("height", &db::Box::height)
        .function("area", &db::Box::area)
        .function("empty", &db::Box::empty);

    // db::DBox
    class_<db::DBox>("DBox")
        .constructor<>()
        .constructor<double, double, double, double>()
        .function("left", &db::DBox::left)
        .function("bottom", &db::DBox::bottom)
        .function("right", &db::DBox::right)
        .function("top", &db::DBox::top)
        .function("width", &db::DBox::width)
        .function("height", &db::DBox::height)
        .function("area", &db::DBox::area)
        .function("empty", &db::DBox::empty);

    // db::Edge
    class_<db::Edge>("Edge")
        .constructor<>()
        .constructor<const db::Point&, const db::Point&>()
        .function("p1", &db::Edge::p1)
        .function("p2", &db::Edge::p2)
        .function("length", &db::Edge::length);

    // db::Polygon
    class_<db::Polygon>("Polygon")
        .constructor<>()
        .constructor<const db::Box&>()
        .function("area", &db::Polygon::area)
        .function("box", &db::Polygon::box);

    // db::Region
    class_<db::Region>("Region")
        .constructor<>()
        .constructor<const db::Box&>()
        .constructor<const db::Polygon&>()
        .function("area", &db::Region::area)
        .function("bbox", &db::Region::bbox)
        .function("empty", &db::Region::empty)
        .function("count", &db::Region::count)
        .function("size", optional_override([](const db::Region& self, db::Coord d) {
            return self.sized(d);
        }))
        .function("and_op", optional_override([](const db::Region& self, const db::Region& other) {
            return self & other;
        }))
        .function("or_op", optional_override([](const db::Region& self, const db::Region& other) {
            return self | other;
        }))
        .function("xor_op", optional_override([](const db::Region& self, const db::Region& other) {
            return self ^ other;
        }))
        .function("not_op", optional_override([](const db::Region& self, const db::Region& other) {
            return self - other;
        }));

    // db::LayerProperties
    class_<db::LayerProperties>("LayerProperties")
        .constructor<>()
        .constructor<int, int>()
        .property("layer", &db::LayerProperties::layer)
        .property("datatype", &db::LayerProperties::datatype);

    // db::Layout
    class_<db::Layout>("Layout")
        .constructor<>()
        .function("dbu", optional_override([](const db::Layout& self) {
            return self.dbu();
        }))
        .function("set_dbu", optional_override([](db::Layout& self, double val) {
            self.dbu(val);
        }))
        .function("cells", optional_override([](const db::Layout& self) {
            return self.cells();
        }))
        .function("layers", optional_override([](const db::Layout& self) {
            return self.layers();
        }))
        .function("insert_layer", optional_override([](db::Layout& self, const db::LayerProperties& props) {
            return self.insert_layer(props);
        }));

    // Helper functions for I/O
    function("loadLayoutFile", &load_layout_file);
    function("saveLayoutFile", &save_layout_file);
}
