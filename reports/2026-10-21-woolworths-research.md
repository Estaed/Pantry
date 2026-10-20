# Woolworths purchases, barcodes and nutrition: research (2026-10-21)

Question: can Woolworths be handled like Coles in Pantry, meaning (a) Tarık's purchases item by item,
in-store and online, read from his logged-in browser, and (b) each product's EAN plus per 100 g
nutrition for `doc.catalogue`? No account was logged in and none of Tarık's accounts were used.

How it was checked: official Everyday Rewards help text, read live on 2026-10-21; the source code of
four public GitHub projects that read Everyday Rewards eReceipts (two of them dated 2026); and one
logged-out probe of woolworths.com.au's public product endpoints on 2026-10-21. That probe ran from a
temporary, empty browser profile before the coordinator said not to use a browser. No browser was
used after that message.

## Short answer

- **In-store purchases are on the web, item by item.** They are Everyday Rewards eReceipts at
  `https://www.everyday.com.au/index.html#/my-activity`. A JSON GraphQL API sits behind that page and a
  logged-in tab can call it.
- **Receipt lines carry no stockcode or barcode.** Each line is only `prefixChar`, `description`
  and `amount`, for example `WW Drought Relief Whole Milk 2L`. So a one-time mapping from line text to
  stockcode is needed. The Woolworths search API makes that mapping easy because its results already
  include `Barcode`.
- **The product detail endpoint in notes.md still works.** On 2026-10-21 it returned `Barcode` and a
  per 100 g nutrition table. It needs only the anonymous cookies a normal woolworths.com.au page sets;
  no login is needed. A request with no cookies was reset.
- **Order emails are not verified.** Public sources do not show the sender address or whether the
  items are listed.

## 1. Where past purchases are visible

### In-store: Everyday Rewards eReceipts (verified)

From the official eReceipts page,
<https://www.everyday.com.au/rewards/how-it-works/ereceipts.html>, read 2026-10-21 (page © 2026):

- "Every time you shop and scan your Everyday Rewards Card in-store at Woolworths, BIG W & BWS, your
  eReceipt will automatically be saved in your Everyday Rewards app **and online account**."
- "You can view your eReceipts for **14 months** after your shop. Plus, you can download them."
  Coverage runs from 1 May 2020 for Woolworths.
- Viewing online: "In the 'My Activity' section of your Everyday Rewards online account … Select 'My
  Account' followed by 'My Activity' … Click on the receipt icon or date section … to view your
  eReceipt."
- The receipt shows "Purchases and savings in-store" and "Tax invoices".
- Condition: the card must be scanned at the till. A shop without the card gets no eReceipt.
- The Everyday Rewards site has moved from `everydayrewards.com.au` to `everyday.com.au`. The old
  `/ereceipts` URL returns a 301 redirect to `www.everyday.com.au/ereceipts` (checked 2026-10-21).
- The App Store listing and old APKMirror notes say receipts are kept for 90 days. The official
  14-month figure overrides that. The Paper Keep guide, updated 2026-09-06, also gives 14 months:
  <https://thepaperkeep.com/resources/find-woolworths-receipt>.

**So the in-store history is reachable on the web, not only in the app.**

### The JSON behind the web page (verified from 2026 code, not run against a real account)

| Item | Value | Source |
|---|---|---|
| Page | `https://www.everyday.com.au/index.html#/my-activity` | bohemian-miser/woolies-receipts README, 2026-06-22 |
| Endpoint | `POST https://apigee-prod.api-wr.com/wx/v1/bff/graphql` | the same repo, plus ekutilov/au.msd.receiptreader config of 2026-07-06 |
| Headers | `authorization: Bearer <access_token>`, `client_id: 8h41mMOiDULmlLT28xKSv5ITpp3XBRvH`, `Content-Type: application/json` | both repos; the client_id has been the same since up_woolies (2022) |
| Token | In the logged-in everyday.com.au tab, `JSON.parse(localStorage.authStatusData).access_token`, with `accessTokenExpired === 'N'` while it is valid | receiptreader `esm/src/connectors/everyday/connector.js` |
| Purchase list | `rtlRewardsActivityFeed(pageToken:"FIRST_PAGE", featureFlags:{…}, enableOnlineReceipt:true)`, paged with `nextPageToken`. Each item has `receipt{receiptId receiptSource}` | receiptreader `configs/connectors.conf.json` |
| One receipt | `activityDetails(id: base64(JSON.stringify(item.receipt)))`. In-store results come back as `ReceiptDetails`, whose `ReceiptDetailsItems.items[]` hold `{prefixChar, description, amount}`, plus a header (`storeNo`), a footer (`transactionDetails` with time and date), payments, and `download{url filename}` for the PDF | same config, same connector |
| Online orders in the same feed | With `enableOnlineReceipt:true`, online orders appear as `OnlineReceiptDetails`, with `OnlineReceiptDepartmentCard.departmentBlocks[].departmentItems[]{description value}` plus substitution and out-of-stock cards | same config, same connector; woolies-receipts says it parses both online and in-store |
| Token life | The bearer token expires after about 30 minutes. That figure is from 2022; it is not verified for 2026 | up_woolies README |

Format of the receipt lines, seen in all the parsers:

- A multi-buy shows as a name line followed by `Qty 2 @ $6.00 each`.
- A weighed item shows as a name line followed by `0.716 kg NET @ $4.00/kg`.
- A discount is a line with a negative amount, or `PRICE REDUCED BY $3.15 each`.
- Some names start with `#`, `*` or `^`. That is the `prefixChar` field, and its meaning is unknown.
- **No line has a stockcode, SKU or barcode.** receiptreader sets `sku: undefined` for Woolworths,
  and the GraphQL fragment `receiptLineItem` has only those three fields.

Sources (repo creation or last-push date):

- <https://github.com/ekutilov/au.msd.receiptreader>, config committed 2026-07-06, pushed 2026-08-09
- <https://github.com/bohemian-miser/woolies-receipts>, 2026-06-22
- <https://github.com/T-Fowl/everyday-rewards-receipts>, pushed 2024-05-24
- <https://github.com/MattTimms/up_woolies>, 2021 to 2023. It reports that the email and password
  login endpoint was shut off and that MFA is now required. Only a token from a real browser login
  works.

### Online orders on woolworths.com.au "My orders" (partly verified)

- The page is `https://www.woolworths.com.au/shop/myaccount/myorders`. Logged out, it redirects to
  `/shop/securelogin` (probe, 2026-10-21). The page lists every item; a 2025 userscript reads the
  `wow-my-order-groceries-list-item-v2` elements:
  <https://github.com/lemonteaau/OZ-Supermarket-Bill-Splitter> (pushed 2025-08-12).
- **The JSON endpoint is not verified.** The public site bundle (`main.70f6e2c2187cc8e7.js`, loaded
  2026-10-21) contains `/api/v3/ui/invoices`, `/api/v3/ui/invoices/search` and `/api/orderworkflow`.
  These are the likely order-history calls, but nothing was called with an account. It is also not
  verified whether the order lines carry a stockcode, though order pages normally link each product.
- Online orders also appear in the Everyday Rewards feed, as described above, but there the lines
  have no stockcode either.

## 2. From a receipt line to barcode and per 100 g nutrition (verified 2026-10-21)

Two calls were made from a logged-out page on woolworths.com.au, in the page context, using only the
anonymous cookies the site sets: `_abck`, `bm_sz`, `ak_bmsc`, and a guest `wow-auth-token`.

1. **Search:** `POST /apis/ui/Search/products` with
   `{"SearchTerm":"tuna chunks in springwater","PageSize":5,"PageNumber":1,"SortType":"TraderRelevance","Location":"/shop/search/products?searchTerm=tuna"}`
   returned HTTP 200. Results are in `Products[].Products[]`, and each carries `Stockcode`, `Name`,
   `Barcode` and `PackageSize`. One example was
   `6047799 Woolworths Tuna Chunks In Springwater, 9339687435784, 185g`.
2. **Detail:** `GET /apis/ui/product/detail/340411?isMobile=false` returned HTTP 200 with:
   - `Product.Barcode = "9300462346120"` and `PackageSize = "95g"`.
   - `NutritionalInformation[]`, where each row is `{Name, Values{"Quantity Per Serving", "Quantity Per 100g / 100mL"}, ServingSize, ServingsPerPack}`.
     The example row was `Energy 474.0kJ` per 100 g; Protein, Fat, Saturated, Carbohydrate, Sugars,
     Fibre and Sodium follow the same pattern.
   - The same values again under `AdditionalAttributes.nutritionalinformation`, as a JSON string with
     named attributes such as `Carbohydrate Quantity Per 100g - Total - NIP`.
   - Other top-level keys: `Nutrition`, `AdditionalAttributes`, `PrimaryCategory`, `CountryOfOriginLabel`.

Things to plan for:

- **Energy is in kJ.** Divide by 4.184 for kcal.
- **Values can be `"< 1.0g"` or `"-"`.** Following the project's real-data rule, `-` stays missing
  and `< 1.0` is kept as written or flagged; it is not changed into a number.
- **Cookies are needed.** A plain request to the same URL with no cookies was reset (ECONNRESET),
  which is the Akamai bot manager. An earlier plain `curl` hung. So the catalogue tool has to run its
  `fetch` from an open woolworths.com.au tab, the same way the Coles route works. **No login is
  needed.**

## 3. Order confirmation emails (not verified)

- No public source gives the sender address of Woolworths AU order confirmation or invoice emails, or
  shows whether they list the items. Searches on 2026-10-21 for `noreply@`, `no-reply@` and
  `onlineshopping@woolworths.com.au` found nothing.
- Woolworths NZ says it sends "order confirmation and invoice emails" by law
  (<https://www.woolworths.co.nz/help/faqs>, read 2026-10-21). For AU this is likely but not verified.
- In-store eReceipts are not emailed as far as the official help page says. It names only the app and
  the online account.
- **To settle it:** the main loop searches Tarık's Gmail for
  `from:(woolworths.com.au OR everyday.com.au) newer_than:2y` and reads one message.

## 4. Terms-of-use risk, in one line

The woolworths.com.au terms ("Site conditions of use", section 1.4) prohibit using any "robot,
spider or similar search and retrieval tool" on the site. That comes from a search-engine summary of
<https://www.woolworths.com.au/shop/services/terms-and-conditions>, whose cached copy is about a year
old; the page itself returned 403 to the fetcher. So reading your own receipts by hand in a logged-in
tab is low risk, but a scheduled, unattended scraper breaches those terms. The realistic penalty is
the account being blocked or suspended, which Everyday Rewards reserves for "abuse"; that is not
verified for the Everyday Rewards terms themselves.

## Recommended route for the main loop (in Tarık's logged-in Opera)

1. **Purchases (both stores' style, one export).** Tarık logs in at
   `https://www.everyday.com.au/index.html#/my-activity`. In that tab's DevTools console, run one
   script that:
   - reads `JSON.parse(localStorage.authStatusData).access_token`;
   - pages through `rtlRewardsActivityFeed` from `FIRST_PAGE`, following `nextPageToken`, with
     `enableOnlineReceipt:true`;
   - calls `activityDetails` for every item that has a `receipt`, sending the `client_id` header above;
   - saves the raw JSON to `Estaed/Pantry-Data`, never to this repo.

   That covers 14 months of in-store shops plus online orders. First check that a request from the
   console is allowed: the page makes the same cross-origin call itself, so it should be. If it is not,
   copy the responses from the Network tab (`graphql`) instead.
2. **Normalise.** Build one purchase per name line: join the `Qty n @` and `kg NET @` follow-up
   lines, subtract the negative discount lines, and keep `prefixChar`.
3. **Map line to stockcode, once.** From an ordinary woolworths.com.au tab (no login needed), send
   each distinct receipt description to `POST /apis/ui/Search/products`. Take the top hit only when the
   name and size clearly match, and show the rest to Tarık to choose. Store the mapping
   `description → stockcode` in the data repo, so each line text is resolved once.
4. **Catalogue.** For each mapped stockcode, call `GET /apis/ui/product/detail/{stockcode}` from the
   same tab, and write `{barcode, name, brand, size, store:"woolworths", per100}` (kJ converted to
   kcal) into `doc.catalogue`.
5. **Optional, later.** Open `woolworths.com.au/shop/myaccount/myorders` with the Network tab open and
   see whether `/api/v3/ui/invoices…` returns order lines with stockcodes. If it does, online orders can
   skip step 3. Also run the Gmail search in section 3.

Keep the export as a manual, one-click run started by Tarık in his own tab. Do not run it unattended:
the bearer token is short-lived, login needs MFA, and the site terms forbid automated retrieval.
