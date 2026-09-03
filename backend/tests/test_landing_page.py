from app.landing_page import _MetadataParser, _first_product


def test_landing_parser_extracts_product_jsonld():
    parser = _MetadataParser()
    parser.feed(
        """
        <html>
          <head>
            <title>Example Phone</title>
            <meta name="description" content="Example phone">
            <meta property="og:image" content="https://example.com/phone.jpg">
            <link rel="canonical" href="https://example.com/product/phone">
            <script type="application/ld+json">
              {"@context":"https://schema.org","@type":"Product","name":"Example Phone",
               "brand":{"@type":"Brand","name":"Example"},
               "sku":"P-123","offers":{"@type":"Offer","price":"49999","priceCurrency":"INR"}}
            </script>
          </head>
        </html>
        """
    )

    product = _first_product(parser.json_ld)

    assert product["name"] == "Example Phone"
    assert product["brand"]["name"] == "Example"
    assert parser.canonical.endswith("/product/phone")
    assert parser.meta[("property", "og:image")] == "https://example.com/phone.jpg"


def test_first_product_handles_graph():
    product = _first_product([
        '{"@graph":[{"@type":"Organization","name":"Example"},{"@type":"Product","name":"Widget"}]}'
    ])
    assert product["name"] == "Widget"
