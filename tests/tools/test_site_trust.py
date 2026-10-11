from openjarvis.tools.site_trust import _extract_domain


def test_plain_domains():
    assert _extract_domain("amazon.es") == "amazon.es"
    assert _extract_domain("https://amazon.com/x") == "amazon.com"
    assert _extract_domain("www.zalando.de") == "zalando.de"


def test_two_label_public_suffixes_keep_the_real_shop_domain():
    # Before the fix, these all collapsed to the registry's own apex ("co.uk", "com.au"...),
    # so a check on a .co.uk shop reported on the UK registry, not the shop.
    assert _extract_domain("shop.co.uk") == "shop.co.uk"
    assert _extract_domain("https://tienda.com.es/producto") == "tienda.com.es"
    assert _extract_domain("www.store.com.au") == "store.com.au"
    assert _extract_domain("deals.co.jp") == "deals.co.jp"


def test_invalid_input():
    assert _extract_domain("") is None
    assert _extract_domain("not a domain") is None
