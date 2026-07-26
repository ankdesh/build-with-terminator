"""
converter.py
============
Core IP-XACT 2014 → 2022 conversion engine.

Performs the following operations in strict sequence:
  1. Parse the input XML using lxml (preserving structure, removing blank text for pretty-print).
  2. Rebuild the root element with the 2022 namespace map.
  3. Migrate all element tags from the 2014 namespace to the 2022 namespace recursively.
  4. Normalize <ipxact:vendor> to the configured target_vendor ('saiti').
  5. Extract deprecated <ipxact:isPresent> elements and wrap them in Accellera Vendor Extensions.
  6. Scan all elements and emit stderr warnings (Cat 3) or info (Cat 2) for out-of-profile elements.
  7. Serialize the result with pretty-print, UTF-8, and an XML declaration.
"""

import sys
from pathlib import Path
from typing import Optional

try:
    from lxml import etree
except ImportError:
    print(
        "CRITICAL ERROR: 'lxml' is required. Install with: uv add lxml",
        file=sys.stderr,
    )
    sys.exit(1)

from src.tools.converter.element_categories import (
    CATEGORY_2_ELEMENTS,
    CATEGORY_3_ELEMENTS,
)

# ---------------------------------------------------------------------------
# Namespace constants
# ---------------------------------------------------------------------------
NS_2014: str = "http://www.accellera.org/XMLSchema/IPXACT/1685-2014"
NS_2022: str = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
NS_XSI: str = "http://www.w3.org/2001/XMLSchema-instance"
NS_ACC: str = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022-VE"
NS_ACC_COND: str = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022-VE-COND-1.0"

# Default namespace map applied to the output root element.
OUTPUT_NS_MAP: dict[str, str] = {
    "ipxact": NS_2022,
    "xsi": NS_XSI,
    "accellera": NS_ACC,
    "accellera-cond": NS_ACC_COND,
}


class IPXACTConverter:
    """
    Converts an IP-XACT IEEE 1685-2014 XML document to IEEE 1685-2022.

    Usage:
        converter = IPXACTConverter(target_vendor="saiti")
        converter.convert(input_path=Path("old.xml"), output_path=Path("new.xml"))
    """

    def __init__(self, target_vendor: str = "saiti") -> None:
        """
        Args:
            target_vendor: The vendor string to enforce in all <ipxact:vendor> elements.
                           Defaults to 'saiti' per organizational convention.
        """
        self.target_vendor = target_vendor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(self, input_path: Path, output_path: Path) -> None:
        """
        Full conversion pipeline from 2014 to 2022.

        Args:
            input_path: Path to the source IP-XACT 2014 XML file.
            output_path: Destination path for the generated 2022 XML file.

        Raises:
            FileNotFoundError: If input_path does not exist.
            ValueError: If the file cannot be parsed as valid XML.
        """
        if not input_path.is_file():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        print(f"[*] Ingesting: '{input_path}'", file=sys.stderr)

        # Step 1: Parse — remove_blank_text lets lxml pretty-print cleanly later.
        parser = etree.XMLParser(remove_blank_text=True)
        try:
            tree = etree.parse(str(input_path), parser)
        except etree.XMLSyntaxError as exc:
            raise ValueError(f"Failed to parse '{input_path}': {exc}") from exc

        root = tree.getroot()

        # Step 2: Rebuild root with 2022 namespace map.
        new_root = self._rebuild_root(root)
        tree._setroot(new_root)  # type: ignore[attr-defined]

        # Step 3: Migrate all 2014-namespaced elements to 2022.
        self._migrate_namespaces(new_root)

        # Step 3b: Remove stale namespace declarations (ns0, ns1...) that lxml
        # leaves behind on child elements after in-place tag reassignment.
        etree.cleanup_namespaces(new_root, top_nsmap=OUTPUT_NS_MAP)

        # Step 4: Normalize vendor identity.
        vendor_count = self._normalize_vendor(new_root)
        print(
            f"[*] Normalized {vendor_count} <ipxact:vendor> element(s) → '{self.target_vendor}'",
            file=sys.stderr,
        )

        # Step 5: Translate deprecated isPresent → Accellera Vendor Extensions.
        cond_count = self._translate_is_present(new_root)
        print(
            f"[*] Translated {cond_count} <isPresent> element(s) into Accellera Vendor Extensions",
            file=sys.stderr,
        )

        # Step 6: Flag Category 2 / Category 3 elements to stderr.
        self._flag_out_of_profile_elements(new_root)

        # Step 6b: Final namespace cleanup — removes any remaining stale ns* prefixes
        # that lxml attaches to SubElement nodes created during VE injection.
        etree.cleanup_namespaces(new_root, top_nsmap=OUTPUT_NS_MAP)

        # Step 7: Serialize output.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(
            str(output_path),
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )
        print(f"[*] Output written to: '{output_path}'", file=sys.stderr)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rebuild_root(self, old_root: etree._Element) -> etree._Element:
        """
        Construct a new root element with the correct 2022 namespace map,
        then migrate all children and attributes from the legacy root.
        """
        local_name = etree.QName(old_root.tag).localname
        new_root = etree.Element(
            etree.QName(NS_2022, local_name),
            nsmap=OUTPUT_NS_MAP,
        )

        # Transfer attributes — replace 2014 URLs in schemaLocation with 2022.
        for attr_name, attr_value in old_root.attrib.items():
            if "schemaLocation" in attr_name:
                attr_value = attr_value.replace(NS_2014, NS_2022)
            new_root.set(attr_name, attr_value)

        # Attach all child elements from the old root.
        new_root.extend(list(old_root))
        return new_root

    def _migrate_namespaces(self, root: etree._Element) -> None:
        """
        Walk every element in the tree. Any element in the 2014 namespace
        is rebounded to the 2022 namespace in-place.
        """
        for elem in root.iter():
            if not isinstance(elem.tag, str):
                # Skip processing instructions and comments.
                continue
            qname = etree.QName(elem.tag)
            if qname.namespace == NS_2014:
                elem.tag = f"{{{NS_2022}}}{qname.localname}"

    def _normalize_vendor(self, root: etree._Element) -> int:
        """
        Find all <ipxact:vendor> elements and overwrite their text with target_vendor.

        Returns:
            Number of vendor elements updated.
        """
        vendor_elements = root.xpath(
            ".//ipxact:vendor", namespaces={"ipxact": NS_2022}
        )
        for elem in vendor_elements:
            elem.text = self.target_vendor
        return len(vendor_elements)

    def _translate_is_present(self, root: etree._Element) -> int:
        """
        Find all (now 2022-namespaced) <ipxact:isPresent> elements — which are
        illegal in the 2022 core schema — and restructure them into the
        Accellera Vendor Extensions block.

        The VE wrapper element name matches the local name of the element's parent
        (e.g., a <port> parent → <accellera:port> wrapper).

        Returns:
            Number of isPresent elements translated.
        """
        is_present_elements: list[etree._Element] = root.xpath(
            ".//ipxact:isPresent", namespaces={"ipxact": NS_2022}
        )
        count = 0

        for is_present in is_present_elements:
            parent = is_present.getparent()
            if parent is None:
                # Orphaned element — skip safely.
                continue

            parent_local_name = etree.QName(parent.tag).localname

            # Cache the expression and remove the deprecated tag.
            condition_expression: Optional[str] = is_present.text
            parent.remove(is_present)

            # Locate or create <ipxact:vendorExtensions> inside the parent.
            vendor_ext_tag = f"{{{NS_2022}}}vendorExtensions"
            vendor_extensions = parent.find(vendor_ext_tag)
            if vendor_extensions is None:
                vendor_extensions = etree.SubElement(parent, vendor_ext_tag)

            # Create <accellera:{parent_local_name}> contextual wrapper.
            wrapper_tag = f"{{{NS_ACC}}}{parent_local_name}"
            accellera_wrapper = vendor_extensions.find(wrapper_tag)
            if accellera_wrapper is None:
                accellera_wrapper = etree.SubElement(vendor_extensions, wrapper_tag)

            # Inject <accellera-cond:isPresent> with the original expression.
            cond_elem = etree.SubElement(
                accellera_wrapper, f"{{{NS_ACC_COND}}}isPresent"
            )
            cond_elem.text = condition_expression
            count += 1

        return count

    def _flag_out_of_profile_elements(self, root: etree._Element) -> None:
        """
        Scan all elements and emit structured warnings / info messages to stderr:
          - Category 3 elements → WARNING (incompatible with lean profile)
          - Category 2 elements → INFO (optional; outside Phase 1 scope)
        """
        seen_cat3: set[str] = set()
        seen_cat2: set[str] = set()

        for elem in root.iter():
            if not isinstance(elem.tag, str):
                continue
            local = etree.QName(elem.tag).localname

            if local in CATEGORY_3_ELEMENTS and local not in seen_cat3:
                print(
                    f"[WARNING][Cat3] <{local}>: {CATEGORY_3_ELEMENTS[local]}",
                    file=sys.stderr,
                )
                seen_cat3.add(local)

            elif local in CATEGORY_2_ELEMENTS and local not in seen_cat2:
                print(
                    f"[INFO][Cat2]    <{local}>: {CATEGORY_2_ELEMENTS[local]}",
                    file=sys.stderr,
                )
                seen_cat2.add(local)

        if seen_cat3:
            print(
                f"[WARNING] {len(seen_cat3)} Category 3 element type(s) found — "
                "these are incompatible with the lean intra-core profile and should be removed.",
                file=sys.stderr,
            )
        if seen_cat2:
            print(
                f"[INFO] {len(seen_cat2)} Category 2 element type(s) found — "
                "these are optional and outside Phase 1 scope.",
                file=sys.stderr,
            )
