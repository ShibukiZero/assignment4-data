## Problem `look_at_cc`: Looking at the Data (4 points)

### (a)
**Question:** Download the WARC file above, or find the copy we provide on the cluster. Look at the very first web page in the file. What is its URL? Is it still accessible? Can you tell what the page seems to be about by looking at the raw HTML?

**Deliverable:** A 2-3 sentence response.

**Answer:** The first web page in the WARC file is `http://0371rykj.com/ipfhsb/34.html`. When I checked it on April 9, 2026, it was still accessible, although it redirected to `http://www.0371rykj.com/ipfhsb/34.html` before returning `200 OK`. From the raw HTML, the page appears to be a Chinese industrial equipment company page, but its title and meta tags look inconsistent with the body content and appear to contain suspicious keyword stuffing, which suggests that the page may be polluted by SEO spam or other low-quality web content.

### (b)
**Question:** Look at the corresponding WET file. Are there parts of the extracted text that should have been filtered out by the extractor? What might go wrong when training a model on text that looks like this? Conversely, what useful information can a model potentially extract from this page?

**Deliverable:** A 3-4 sentence response.

**Answer:** Yes. The extracted text still contains a lot of content that should likely have been filtered out, including spammy keyword strings at the top, navigation items, contact information, repeated category lists, and footer-like boilerplate such as previous/next links and copyright text. Training on text like this could cause a model to learn low-value webpage templates, keyword stuffing, and repetitive site-specific fragments instead of clean natural language. At the same time, the page still contains some useful information, such as the company name, the product description, and technical specifications for the equipment, which could help the model learn domain-specific vocabulary and factual technical language.

### (c)
**Question:** Describe an application domain for which this example might be useful to have in the training data, and one where it might not be.

**Deliverable:** A 1-2 sentence response.

**Answer:** This example could be useful for a domain-specific system focused on Chinese industrial equipment, product catalogs, or technical retrieval, because it contains real company information, product descriptions, and equipment specifications. It would be much less suitable for training a general-purpose user-facing language model, since the page also contains spammy keywords, boilerplate navigation text, and other low-quality web artifacts.

### (d)
**Question:** Look through 25 more WET records. For each record, briefly comment on the document's language, domain name, page type, and any other notable observations. How many examples does it take until you see what you would deem a high-quality webpage?

**Deliverable:** Brief annotations of 25 documents, plus the number of examples it takes until you see a high-quality example.

**Answer:** The first clearly high-quality webpage appeared at record 2, which is the USNCCM13 conference homepage. Many of the other early examples are dominated by spam, adult content, templated portals, error pages, or low-value navigation-heavy pages, although a few later records are also reasonably high-quality informational pages.

| # | Language | Domain | Page type | Notes |
| --- | --- | --- | --- | --- |
| 1 | Chinese | `10www.chinatikfans.com` | Discuz fan blog / forum page | Mostly login and navigation boilerplate; little substantive content visible in the preview. |
| 2 | English | `13.usnccm.org` | Conference homepage | Clear event information, location, and menu structure; looks like a legitimate informational site. |
| 3 | Chinese | `176.utchat888.com` | Adult video chat portal | Explicit adult gating, rankings, and payment-oriented portal text. |
| 4 | Chinese | `176766.cn` | Spammy company / product page | Starts with explicit spam keywords, then switches into generic company-site navigation. |
| 5 | Chinese | `178mh.com` | Broken template / error page | Only shows a missing-template message, so it has almost no useful textual content. |
| 6 | Chinese | `1796370.tgtg97.com` | Adult cam host profile | Repetitive rankings, pricing, and chat-room boilerplate dominate the page. |
| 7 | Chinese | `18sex.v340.info` | Adult portal landing page | Explicit sexual content plus repeated promotional and ranking text. |
| 8 | Dutch | `1kb.klimtoren.be` | Personal or school blog post | A short blog entry with some boilerplate, but still a recognizable human-written post. |
| 9 | Greek | `1pekesat-exae.mysch.gr` | Helpdesk search page | Mostly forum/search navigation text; low information density in this preview. |
| 10 | Greek | `1pekesat-exae.mysch.gr` | Helpdesk login page | Almost entirely login and site-navigation boilerplate. |
| 11 | Chinese | `1s6605084.yhxzseo.com` | SEO-style content page | Looks like a templated landing page with some readable article text mixed in. |
| 12 | Turkish | `20com20.fr` | Documentation sitemap | Legitimate technical documentation, though it is mainly navigational rather than prose-heavy. |
| 13 | English | `24ktcasino.net` | Casino blog post | Commercial gambling content with blog framing; some natural language but domain is narrow and promotional. |
| 14 | English | `2kgames.eu` | Error page | Just a 404 page, so it is low-value training text. |
| 15 | Chinese | `2l6185919.yizhangting.com` | SEO / entertainment landing page | Templated portal-style page with broad category links and vague promotional text. |
| 16 | Chinese | `303323.com` | Medical device company news page | Legitimate company/news content, but still heavy on navigation and contact boilerplate. |
| 17 | Chinese | `30bad.com` | Streaming / anime aggregator page | Media-index page with synopsis and navigation, not very content-rich. |
| 18 | Chinese | `312001.net` | Hospital / clinic news page | Legitimate institutional site, but the preview is mostly navigation categories rather than article text. |
| 19 | Chinese | `354577.mwe075.com` | Dating / video chat portal | Ranking tables, login prompts, and host-status text dominate the page. |
| 20 | English | `356.schoollibrary.edu.pe.ca` | Library catalog search results page | Legitimate educational site, but this particular page is a noisy no-results catalog query. |
| 21 | Chinese | `366392.haaxz.com` | Adult video portal page | Explicit adult categories and repetitive monetized portal text. |
| 22 | Chinese | `366392.haaxz.com` | Adult video portal page | Near-duplicate of the previous portal page with different host/persona details. |
| 23 | Chinese | `387tel.com` | Video chat / dating portal | Mostly account and ranking UI text, with little substantive prose. |
| 24 | Spanish | `3diasdemarzo.blogspot.com` | News / opinion blog post | Long coherent article text about a specific political issue; comparatively high-quality prose. |
| 25 | Danish | `3godetilbud.dk` | Commercial service landing page | Lead-generation page with short marketing copy and strong call-to-action language. |

High-quality example first appeared at: record 2

---

## Problem `extract_text`: HTML to Text Conversion (3 points)

### (b)
**Question:** Run your text extraction function on a single WARC file. Compare its output to the extracted text in the corresponding WET file. What differences and/or similarities do you notice? Which extraction seems better?

**Deliverable:** A 2-3 sentence response comparing and contrasting the two extracted texts.

**Answer:** Our extraction and the Common Crawl WET output recover much of the same underlying page content, including the product-related text and some of the same spammy or low-quality material. However, our extraction is much noisier: it preserves many HTML-structure artifacts, bullets, and template-like fragments that make the text substantially longer and less readable. For this example, the WET extraction seems better overall, because it is more compact and cleaner, even though it still retains some undesirable boilerplate.

---

## Problem `language_identification`: Language Identification (6 points)

### (a)
**Question:** Write a function that takes a Unicode string and identifies the main language present in the string. Your function should return a pair containing a language identifier and a confidence score between 0 and 1.

**Deliverable:** A function that performs language identification, giving its top language prediction and a score.

**Answer:** We use the pre-trained fastText `lid.176.bin` language identification model. Our function returns the top language prediction and its confidence score, with adapter-side label normalization for outputs such as `en` and `zh`.

---

### (b)
**Question:** What issues could arise downstream from problems in the language identification procedure? In a higher-stakes scenario, how would you mitigate these issues?

**Deliverable:** A 2-5 sentence response.

**Answer:** Errors in language identification can distort the training distribution in both directions: false positives can let non-target-language pages, mixed-language pages, or noisy template text into the dataset, while false negatives can remove useful in-language documents and reduce coverage of important domains or dialects. As a result, the final language model may generate more mixed-language or low-quality text, and it may underperform on legitimate examples that were filtered out too aggressively. In a higher-stakes setting, I would not rely on a single hard language-ID decision alone; instead, I would combine confidence thresholds, manual audits of borderline cases, and additional signals such as document length or character distribution, while also monitoring downstream behavior for systematic errors.

### (c)
**Question:** Run your language identification system on text extracted from the WARC files. Manually identify the language in 20 random examples and compare your labels with the classifier predictions. Report any classifier errors. What fraction of documents are English? Based on your observations, what would be a suitable classifier confidence threshold to use in filtering?

**Deliverable:** A 2-5 sentence response.

**Answer:** In a manual review of 20 randomly sampled extracted documents, the classifier agreed with our labels on 19 of 20 examples. The clearest error was a corrupted PDF-like sample that was predicted as English with low confidence (`0.15`), even though the extracted text was largely non-linguistic garbage rather than clean natural-language content. Overall, `11/20` documents (`55%`) were English. Based on this audit, a confidence threshold around `0.4` seems reasonable: it would remove the obvious failure case while still keeping several correct but noisy boilerplate-heavy pages whose confidence scores were only around `0.47-0.51`.

---

## Problem `mask_pii`: Personal Identifiable Information (3 points)

### (4)
**Question:** What problems might arise downstream in a language model when these filters are naively applied on the training set? How might you mitigate these issues?

**Deliverable:** A 2-5 sentence response.

**Answer:** Naive PII masking can fail in both directions: it can miss real sensitive information, but it can also over-mask benign text such as code, configuration strings, example data, or technical documentation that happens to resemble an email address, phone number, or IP address. Excessive masking can also damage useful semantics by replacing information that is important for understanding customer support text, networking tutorials, or contact instructions, and it may cause the model to overproduce artificial placeholder strings. To mitigate these issues, I would combine conservative pattern design with manual audits, inspect false positives and false negatives on real web data, and use context-aware or document-type-aware rules when possible instead of relying on a single broad regex alone.

### (5)
**Question:** Run your PII masking functions on text extracted from the WARC files. Look through 20 random examples where a replacement was made; give some examples of false positives and false negatives.

**Deliverable:** A 2-5 sentence response.

**Answer:** In a manual review of 20 sampled documents where at least one replacement occurred, most of the obvious matches were reasonable, but we still observed both false positives and false negatives. The clearest false positive came from a corrupted PDF-like sample, where binary garbage produced strings such as `E@NH.oB` that matched the email regex even though they were not real email addresses. We also observed false negatives for phone numbers: for example, the current pattern missed some non-US or more irregular local formats such as `0577-86809666 86809777`, and it did not consistently capture variants with leading digits such as `0321 4115583`. These examples suggest that regex-based masking is useful as a first pass, but brittle on noisy web text and incomplete across international formatting conventions.

---

## Problem `harmful_content`: Harmful Content (6 points)

### (3)
**Question:** What problems might arise downstream in a language model when these filters are applied to create the training set? How might you mitigate these issues?

**Deliverable:** A 2-5 sentence response.

**Answer:** Harmful-content filtering can fail in both directions: it can miss genuinely toxic or NSFW material, but it can also remove legitimate text that discusses these topics in educational, journalistic, policy, or support contexts. If applied too aggressively, such filtering can distort the training distribution, disproportionately remove some styles or communities, and even make the model worse at recognizing, discussing, or safely responding to harmful content because it has seen too little of it in context. To mitigate this, I would avoid relying on a single hard classifier decision, combine confidence thresholds with manual audits of borderline cases, and distinguish between text that merely mentions harmful content and text that is itself primarily harmful.

### (4)
**Question:** Run your harmful-content filters on text extracted from the WARC files. Look through 20 random examples and compare the classifier predictions to your own judgments. Report any classifier errors. What fraction of documents are harmful? Based on your observations, what would be suitable classifier confidence threshold(s) to use in filtering?

**Deliverable:** A 2-5 sentence response.

**Answer:** In a manual review of 20 randomly sampled extracted documents, 19 of 20 classifier decisions matched my judgment. The clearest error was a likely false negative: an Arabic forum thread describing sexual assault and explicit images was labeled `non-nsfw` and `non-toxic` despite containing clearly disturbing sexual content in context. Across the full scanned sample, the filters marked `277 / 27,201` eligible documents (`1.02%`) as harmful by at least one classifier, so harmful pages appear to be relatively rare in this slice of the crawl. Given that several clearly benign pages still had only moderate non-harmful confidence, I would use conservative filtering thresholds, such as requiring at least about `0.8` confidence for toxic predictions and about `0.9` for NSFW predictions, while manually auditing borderline cases.

---

## Problem `gopher_quality_filters`: Quality Rules (3 points)

### (b)
**Question:** Run your rule-based quality filter on text extracted from the WARC files. Look through 20 random examples and compare the filter predictions to your own judgment. Comment on any cases where the quality filters differ from your judgments.

**Deliverable:** A 2-5 sentence response.

**Answer:** In a manual review of 20 randomly sampled extracted documents, the Gopher-style rules did catch some clearly low-quality cases, such as a corrupted PDF-like document and an extremely short page consisting mostly of icon names. However, they also passed several pages that I would still consider low-value for language-model training, including a forum registration page, a GitLab topic listing, and a restaurant menu page, because these documents looked formally well-structured even though they were mostly boilerplate or navigation text. The rules also produced a likely false negative on a Chinese novel page, which was rejected mainly because too few tokens contained alphabetic characters; this highlights that the heuristic is biased toward English-like text. Overall, these rules are useful for catching obvious formatting failures, but they are too shallow to reliably separate genuinely high-value prose from templated or multilingual web content.

---

## Problem `filter_data`: Filter Data for Language Modeling (6 points)

### (a)
**Question:** Write a script to filter language modeling data from the provided Common Crawl WET files in parallel. Report the number of examples kept by each filter that you use, so you have a sense of how the filters contribute to the final output data.

**Deliverable:** A script (or sequence of scripts) that filters the provided CC WET files in parallel to produce language modeling data. A written breakdown of what proportion of the discarded examples are removed by each filter step.

**Answer:** We used a sequence of scripts rather than a single monolithic script. In the self-hosted environment, we randomly selected and downloaded 5,000 WET files from `CC-MAIN-2026-12`; this is the same type of Common Crawl WET input as the handout, but not the pre-mounted Together cluster `/data/CC` path. The stage-1 filter (`scripts/filter_cc_wet_stage1.py`) processed WET records in parallel and applied, in order: English language identification with threshold `0.8`, harmful-content filtering, Gopher-style quality rules, a fastText quality classifier with threshold `0.65`, and PII masking for kept documents. Then `scripts/dedup_stage2.py` performed global exact-line deduplication followed by MinHash near-deduplication, and `scripts/tokenize_filtered_data.py` tokenized the final kept text.

The first-stage document filters saw `96,319,279` WET records and kept `9,080,206` documents (`9.43%`). Among the `87,239,073` records discarded in stage 1, the language filter removed the largest share: `76,316,102` records, or `87.48%` of the stage-1 discards. The quality classifier removed `8,181,266` records (`9.38%` of stage-1 discards), the Gopher rules removed `2,699,978` records (`3.09%`), harmful-content filtering removed `41,702` records (`0.048%`), and `25` records were empty after stripping. PII masking did not discard documents, but it modified `3,081,461` kept documents, which is `33.94%` of the stage-1 kept set.

The deduplication stage then processed the `9,080,206` stage-1 kept documents. Exact-line deduplication indexed `1,304,532,231` line instances and removed `1,054,738,707` repeated line instances (`80.85%` of line instances); after this line removal, `452,581` documents became empty and were discarded. MinHash deduplication generated `132,904` candidate duplicate pairs, confirmed `15,287` duplicate pairs, and removed `6,355` additional documents. The final filtered dataset contains `8,621,270` documents, or `8.95%` of the original WET records.

### (b)
**Question:** How long does it take to filter the 5,000 WET files? How long would it take to filter the entire Common Crawl dump (100,000 WETs)?

**Deliverable:** Runtime of the data filtering pipeline.

**Answer:** Excluding Common Crawl download time, filtering the 5,000 WET files took about `33,688.90` seconds, or `9.36` hours, on our self-hosted server. Stage 1, which applied the document-level WET filters bucket by bucket with `24` workers, took `13,203.16` seconds (`3.67` hours) of summed bucket filtering time. Stage 2, which performed global exact-line deduplication and MinHash/LSH near-deduplication, took `20,485.74` seconds (`5.69` hours) with `40` workers. The stage-2 runtime was dominated by MinHash signature preprocessing, which took `17,672.26` seconds (`4.91` hours); LSH candidate generation took another `1,484.43` seconds (`0.41` hours), while the remaining exact-dedup and write-back phases were much smaller.

A simple linear extrapolation from `5,000` to `100,000` WET files multiplies the observed filtering time by `20`, giving about `187.16` hours, or `7.80` days, on similar hardware with the same staged pipeline. We treat this as an order-of-magnitude estimate rather than a guaranteed wall-clock schedule, because our self-hosted download time is network-dependent and not included here, and because larger runs may shift the bottleneck between CPU, memory, and disk I/O.

---

## Problem `inspect_filtered_data`: Inspect Filtered Data (4 points)

### (a)
**Question:** Take five random examples from your filtered dataset. Comment on their quality and whether they would be suitable for language modeling, especially given that the goal is to minimize perplexity on the C4 100 domains benchmark.

**Deliverable:** Five random examples from the final filtered data, plus a 1-2 sentence description of each example and whether it is worthwhile to use for language modeling.

**Answer:** We sampled five examples from the final stage-2 deduplicated dataset using seed `336`. Overall, the sample suggests that the filtered dataset contains several useful long-form or semi-long-form English documents, but it still admits some web boilerplate and commercial navigation text.

| Example | Excerpt | Description | Worth keeping? |
| --- | --- | --- | --- |
| 1 | `Exodus 20:22 ... Bible Commentary` | A Bible verse page with parallel translations and commentary. It is fluent English, but it is repetitive and domain-specific. | Borderline yes: useful as clean English text, but less representative of broad C4-style web domains. |
| 2 | `Manyavar Store in Kankurgachi ... Choose your Shipping Country` | An e-commerce/store page dominated by menus, product categories, and shipping/navigation text. | Mostly no: this is the clearest kept-sample failure, since it is mostly boilerplate rather than natural prose. |
| 3 | `Massachusetts Man Found Guilty ... Capitol Breach` | A news/legal article about a Capitol breach case, with coherent factual prose. | Yes: this is the kind of article-like web text that should help broad-domain language modeling. |
| 4 | `Tips for Hiring Your First Employee` | A business/entrepreneurship tag page containing short article summaries about hiring and performance reviews. | Yes, with caveats: it has some index-page structure, but the retained text is mostly readable topical prose. |
| 5 | `John Hendricks ... co-founded Strike Source` | A biographical page with coherent sentences about a media/news figure and related work. | Yes: this is relatively clean English prose and seems suitable for language modeling. |

### (b)
**Question:** Take five CC WETs that were removed and/or modified by your filtering script. What part of your filtering process removed or modified these documents, and do you think that their removal and/or modification was justified?

**Deliverable:** Five random discarded examples from the original WETs, plus a 1-2 sentence description of each example and whether its removal was justified.

**Answer:** The five sampled removed/modified examples from the review logs were all dropped by stage-2 exact-line deduplication with reason `exact_line_dedup_empty`: after globally repeated lines were removed, no useful unique text remained. This makes the examples especially helpful for checking whether exact-line dedup is removing boilerplate rather than discarding unique prose.

| Example | Excerpt | Removed/modified by | Was it justified? |
| --- | --- | --- | --- |
| 1 | `Diversity Equity Inclusion Belonging Archives ... About Overview` | `exact_line_dedup_empty` | Yes. The page is mostly repeated school navigation, portals, calendars, and menu boilerplate, so dropping it should improve the training set. |
| 2 | `Introducing Manulife InvestChoice ... Our funds` | `exact_line_dedup_empty` | Yes. The sampled text is dominated by fund-site navigation, login prompts, role selectors, and repeated headings rather than article content. |
| 3 | `Default Web Site Page ... SORRY!` | `exact_line_dedup_empty`; the PII masker also replaced an email address with `\|\|\|EMAIL_ADDRESS\|\|\|` before the final drop. | Yes. This is a generic cPanel default page and not useful natural web content for the target benchmark. |
| 4 | `cybersecuritysymposium.com is for sale` | `exact_line_dedup_empty`; the PII masker also replaced a phone number with `\|\|\|PHONE_NUMBER\|\|\|` before the final drop. | Yes. It is a parked-domain sales page with prices, transaction boilerplate, and support text. |
| 5 | `Mansur – male gyrfalcon ... Sponsorship Bronze` | `exact_line_dedup_empty` | Mostly yes, but this is the most borderline removal. It includes a little animal-description prose, but the page is mixed with sponsorship/product-template text and was not unique after exact-line deduplication. |

### (c)
**Question:** If your analysis above motivates further changes to your data pipeline, report any changes and/or iterations of data that you experimented with.

**Deliverable:** A description of data changes and/or iterations that you experimented with.

**Answer:** This inspection did not motivate a final change to the filtering thresholds or deduplication semantics. The kept Manyavar store page shows that some e-commerce and navigation boilerplate still leaks through, so a future iteration could add a stronger navigation/catalog-page filter or domain/template heuristic. However, changing the final pipeline at this point would also risk removing legitimate short article index pages such as the business-blog sample, and the removed examples suggest that exact-line deduplication is already catching many highly templated pages.

Therefore, we kept the final data pipeline unchanged after this inspection. The main iterations we made for the final run were systems-level and semantics-preserving: improving the stage-2 deduplication storage lifecycle, adding an exact-checkpoint resume path, and verifying with a 50-WET A/B check that the optimized implementation matched the older stage-2 behavior.

---

## Problem `tokenize_data`: Tokenize Data (2 points)

### Token count
**Question:** How many tokens are in your filtered dataset?

**Deliverable:** A script to tokenize and serialize your filtered data, and the number of tokens in your produced dataset.

**Answer:** TODO

---

## Problem `train_model`: Train Model (2 points)

### Training result
**Question:** Train a GPT-2 small-shaped language model on your tokenized dataset. What is the best validation loss that your model achieves? Include the associated learning curve and a description of what you did.

**Deliverable:** The best validation loss that was recorded, the associated learning curve, and a description of what you did.

**Answer:** TODO
