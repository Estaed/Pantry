# Catalogue fixtures (tests/test_catalogue.py)

Public product data only, copied verbatim on 2026-10-21 from what the two store sites return for any visitor;
no receipt, order or account data. The receipts the tests use are built in `tests/test_catalogue.py` in the
real shapes.

- `coles-products.json`: product page data (`__NEXT_DATA__` product: id, name, brand, size, gtin, nutrition)
  for six Coles product ids, as the capture keeps it: a tzatziki and a basmati rice with kJ and Cal, a penne
  with kJ only, a Western Star spread whose protein reads "LESS THAN 1 g", a chicken breast sold per kg with
  no gtin, and one page the site's bot check answered instead (`{ "missing": true }`).
- `woolworths-products.json`: `{ search, details }` for four search terms: the site's top 8 results
  (`POST /apis/ui/Search/products`) and the product detail of the top 3 (`GET /apis/ui/product/detail/<stockcode>`):
  a Western Star spread with two equally close results, a microwave basmati rice cup with one clear result,
  a prepacked potato whose detail has no nutrition table, and a penne search that returned no penne.
