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

**Answer:** TODO

---

## Problem `language_identification`: Language Identification (6 points)

### (b)
**Question:** What issues could arise downstream from problems in the language identification procedure? In a higher-stakes scenario, how would you mitigate these issues?

**Deliverable:** A 2-5 sentence response.

**Answer:** TODO

### (c)
**Question:** Run your language identification system on text extracted from the WARC files. Manually identify the language in 20 random examples and compare your labels with the classifier predictions. Report any classifier errors. What fraction of documents are English? Based on your observations, what would be a suitable classifier confidence threshold to use in filtering?

**Deliverable:** A 2-5 sentence response.

**Answer:** TODO

---

## Problem `mask_pii`: Personal Identifiable Information (3 points)

### (4)
**Question:** What problems might arise downstream in a language model when these filters are naively applied on the training set? How might you mitigate these issues?

**Deliverable:** A 2-5 sentence response.

**Answer:** TODO

### (5)
**Question:** Run your PII masking functions on text extracted from the WARC files. Look through 20 random examples where a replacement was made; give some examples of false positives and false negatives.

**Deliverable:** A 2-5 sentence response.

**Answer:** TODO

---

## Problem `harmful_content`: Harmful Content (6 points)

### (3)
**Question:** What problems might arise downstream in a language model when these filters are applied to create the training set? How might you mitigate these issues?

**Deliverable:** A 2-5 sentence response.

**Answer:** TODO

### (4)
**Question:** Run your harmful-content filters on text extracted from the WARC files. Look through 20 random examples and compare the classifier predictions to your own judgments. Report any classifier errors. What fraction of documents are harmful? Based on your observations, what would be suitable classifier confidence threshold(s) to use in filtering?

**Deliverable:** A 2-5 sentence response.

**Answer:** TODO

---

## Problem `gopher_quality_filters`: Quality Rules (3 points)

### (b)
**Question:** Run your rule-based quality filter on text extracted from the WARC files. Look through 20 random examples and compare the filter predictions to your own judgment. Comment on any cases where the quality filters differ from your judgments.

**Deliverable:** A 2-5 sentence response.

**Answer:** TODO

---

## Problem `filter_data`: Filter Data for Language Modeling (6 points)

### (a)
**Question:** Write a script to filter language modeling data from the provided Common Crawl WET files in parallel. Report the number of examples kept by each filter that you use, so you have a sense of how the filters contribute to the final output data.

**Deliverable:** A script (or sequence of scripts) that filters the provided CC WET files in parallel to produce language modeling data. A written breakdown of what proportion of the discarded examples are removed by each filter step.

**Answer:** TODO

### (b)
**Question:** How long does it take to filter the 5,000 WET files? How long would it take to filter the entire Common Crawl dump (100,000 WETs)?

**Deliverable:** Runtime of the data filtering pipeline.

**Answer:** TODO

---

## Problem `inspect_filtered_data`: Inspect Filtered Data (4 points)

### (a)
**Question:** Take five random examples from your filtered dataset. Comment on their quality and whether they would be suitable for language modeling, especially given that the goal is to minimize perplexity on the C4 100 domains benchmark.

**Deliverable:** Five random examples from the final filtered data, plus a 1-2 sentence description of each example and whether it is worthwhile to use for language modeling.

**Answer:** TODO

| Example | Excerpt | Description | Worth keeping? |
| --- | --- | --- | --- |
| 1 | TODO | TODO | TODO |
| 2 | TODO | TODO | TODO |
| 3 | TODO | TODO | TODO |
| 4 | TODO | TODO | TODO |
| 5 | TODO | TODO | TODO |

### (b)
**Question:** Take five CC WETs that were removed and/or modified by your filtering script. What part of your filtering process removed or modified these documents, and do you think that their removal and/or modification was justified?

**Deliverable:** Five random discarded examples from the original WETs, plus a 1-2 sentence description of each example and whether its removal was justified.

**Answer:** TODO

| Example | Excerpt | Removed/modified by | Was it justified? |
| --- | --- | --- | --- |
| 1 | TODO | TODO | TODO |
| 2 | TODO | TODO | TODO |
| 3 | TODO | TODO | TODO |
| 4 | TODO | TODO | TODO |
| 5 | TODO | TODO | TODO |

### (c)
**Question:** If your analysis above motivates further changes to your data pipeline, report any changes and/or iterations of data that you experimented with.

**Deliverable:** A description of data changes and/or iterations that you experimented with.

**Answer:** TODO

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
