## Problem `look_at_cc`: Looking at the Data (4 points)

### (a)
**Question:** Download the WARC file above, or find the copy we provide on the cluster. Look at the very first web page in the file. What is its URL? Is it still accessible? Can you tell what the page seems to be about by looking at the raw HTML?

**Deliverable:** A 2-3 sentence response.

**Answer:** The first web page in the WARC file is `http://0371rykj.com/ipfhsb/34.html`. When I checked it on April 9, 2026, it was still accessible, although it redirected to `http://www.0371rykj.com/ipfhsb/34.html` before returning `200 OK`. From the raw HTML, the page appears to be a Chinese industrial equipment company page, but its title and meta tags look inconsistent with the body content and appear to contain suspicious keyword stuffing, which suggests that the page may be polluted by SEO spam or other low-quality web content.

### (b)
**Question:** Look at the corresponding WET file. Are there parts of the extracted text that should have been filtered out by the extractor? What might go wrong when training a model on text that looks like this? Conversely, what useful information can a model potentially extract from this page?

**Deliverable:** A 3-4 sentence response.

**Answer:** TODO

### (c)
**Question:** Describe an application domain for which this example might be useful to have in the training data, and one where it might not be.

**Deliverable:** A 1-2 sentence response.

**Answer:** TODO

### (d)
**Question:** Look through 25 more WET records. For each record, briefly comment on the document's language, domain name, page type, and any other notable observations. How many examples does it take until you see what you would deem a high-quality webpage?

**Deliverable:** Brief annotations of 25 documents, plus the number of examples it takes until you see a high-quality example.

**Answer:** TODO

| # | Language | Domain | Page type | Notes |
| --- | --- | --- | --- | --- |
| 1 | TODO | TODO | TODO | TODO |
| 2 | TODO | TODO | TODO | TODO |
| 3 | TODO | TODO | TODO | TODO |
| 4 | TODO | TODO | TODO | TODO |
| 5 | TODO | TODO | TODO | TODO |
| 6 | TODO | TODO | TODO | TODO |
| 7 | TODO | TODO | TODO | TODO |
| 8 | TODO | TODO | TODO | TODO |
| 9 | TODO | TODO | TODO | TODO |
| 10 | TODO | TODO | TODO | TODO |
| 11 | TODO | TODO | TODO | TODO |
| 12 | TODO | TODO | TODO | TODO |
| 13 | TODO | TODO | TODO | TODO |
| 14 | TODO | TODO | TODO | TODO |
| 15 | TODO | TODO | TODO | TODO |
| 16 | TODO | TODO | TODO | TODO |
| 17 | TODO | TODO | TODO | TODO |
| 18 | TODO | TODO | TODO | TODO |
| 19 | TODO | TODO | TODO | TODO |
| 20 | TODO | TODO | TODO | TODO |
| 21 | TODO | TODO | TODO | TODO |
| 22 | TODO | TODO | TODO | TODO |
| 23 | TODO | TODO | TODO | TODO |
| 24 | TODO | TODO | TODO | TODO |
| 25 | TODO | TODO | TODO | TODO |

High-quality example first appeared at: TODO

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
