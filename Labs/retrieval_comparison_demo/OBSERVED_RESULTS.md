# Observed results: simple cafe data

Live checks on 5 November 2026. Eight short notes, text-embedding-3-large, Azure AI Search semantic ranker. These are observed rankings, not guaranteed winners.

| Question | Keyword: first note | Vector: first note | Hybrid + rerank: first note | Hybrid winner before reranking |
|---|---|---|---|---|
| Milkshake price | 01-mango-milkshake | 01-mango-milkshake | 01-mango-milkshake | 1 |
| Bring my order to my house | 06-change-of-mind | 04-home-delivery | 04-home-delivery | 3 |
| Sour milkshake refund | 01-mango-milkshake | 07-spoiled-drink | 06-change-of-mind | 3 |
| Changed my mind after opening | 06-change-of-mind | 06-change-of-mind | 06-change-of-mind | 1 |
| Saturday closing time | 08-opening-hours | 08-opening-hours | 08-opening-hours | 1 |
| Wi-Fi password (unsupported) | 06-change-of-mind | 08-opening-hours | 08-opening-hours | 5 |

## What to show in class

- **Easy exact wording:** all three found the mango milkshake price note.
- **Same meaning, different words:** for "bring my order to my house", keyword
  ranked the refund rule first, vector found home delivery, and hybrid reranking
  moved home delivery from fusion rank 3 to rank 1.
- **An honest failure:** for the sour milkshake question, vector selected the
  spoiled-drink exception first. Hybrid reranking placed the general refund rule
  above it. With only one passage, hybrid does not have the best evidence here.
  Increase the count to 2 to supply the exception too. Reranking is not infallible.
- **Simple controls:** all three selected the change-of-mind rule and Saturday
  opening-hours note for their respective questions.
- **Missing information:** no note gives a Wi-Fi password, even though all methods
  return some passages. The answer model should abstain.

This dataset is intentionally tiny and fully readable. It demonstrates word
matching, meaning matching, reranking and evidence selection, not a general
benchmark claiming one method is always best. The app uses real service calls
and has no question-specific ranking overrides or canned answers.

## Answer and UI checks

Gradio started successfully with all 8 notes visible in its dataset panel. For the delivery question with one passage, Keyword abstained; Vector and Hybrid answered yes with the Rs200 minimum, Rs20 fee and service hours. The unsupported Wi-Fi question produced an abstention; its attached citation was not evidence of a password, illustrating why a citation alone is not proof of support. The old IT demo index was retired after the cafe index was verified.
