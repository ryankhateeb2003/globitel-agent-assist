# Chunking Comparison

## Overview

Three chunking strategies were evaluated on the Orange Money FAQ corpus in both English and Arabic:

1. Fixed-size chunking
2. Sentence-based chunking
3. Structure-based chunking

Each strategy was evaluated using chunk statistics and 10 test questions per language.

---

## English

| Strategy  | Chunk Count | Average Characters | Average Tokens | Broken Answer Rate | Answer Survival |
| --------- | ----------: | -----------------: | -------------: | -----------------: | --------------: |
| Fixed     |          35 |              988.3 |          208.1 |         30% (3/10) |      70% (7/10) |
| Sentence  |          33 |              841.1 |          176.9 |         20% (2/10) |      80% (8/10) |
| Structure |         112 |              247.1 |           51.6 |          0% (0/10) |    100% (10/10) |

### English Analysis

The structure-based strategy produced the best answer integrity.

It had:

* 0% broken answers.
* 100% answer survival.
* 112 chunks with an average of 247.1 characters and 51.6 tokens per chunk.

Fixed-size chunking had the highest broken-answer rate at 30%, while sentence-based chunking reduced this to 20%.

---

## Arabic

| Strategy  | Chunk Count | Average Characters | Average Tokens | Broken Answer Rate | Answer Survival |
| --------- | ----------: | -----------------: | -------------: | -----------------: | --------------: |
| Fixed     |          35 |              980.3 |          377.5 |         40% (4/10) |      60% (6/10) |
| Sentence  |          31 |              886.5 |          339.9 |          0% (0/10) |    100% (10/10) |
| Structure |         112 |              244.6 |           94.5 |          0% (0/10) |    100% (10/10) |

### Arabic Analysis

Fixed-size chunking performed worst for answer integrity, with 40% of the tested answers being broken and only 60% surviving intact.

Sentence-based and structure-based chunking both achieved:

* 0% broken answers.
* 100% answer survival.

Structure-based chunking produced substantially smaller chunks than sentence-based chunking, averaging 94.5 tokens compared with 339.9 tokens.

---

## Strategy Selection

Based on the measurements, the selected strategy is:

* **English: Structure-based chunking**
* **Arabic: Structure-based chunking**

For English, structure-based chunking clearly outperformed the other strategies in answer integrity.

For Arabic, sentence-based and structure-based chunking achieved identical answer-integrity results in the 10-question test. Structure-based chunking was selected because the corpus is FAQ-oriented, so keeping each question and its associated answer together creates a natural retrieval unit. It also produces substantially smaller chunks than sentence-based chunking.

The same strategy is therefore used for both languages, but the decision is supported by the measurements rather than assuming that one strategy must work equally well for both languages.
  
  ---------------------------------

  # Test Evidence

The following terminal commands were used to produce the broken-answer and answer-survival results reported in this comparison.

---

## 1. English — Broken Answer Rate

### Terminal command

```powershell
python -c "from app.ingestion.pipeline import extract_document; from app.chunking.chunker import chunk_text; t=extract_document('corpus/en/orange-money.docx'); lines=[x.strip() for x in t.splitlines() if x.strip()]; q=[i for i,x in enumerate(lines) if x.endswith('?')]; pairs=[(lines[i], ' '.join(lines[i+1:q[n+1]])) for n,i in enumerate(q[:-1])]; pairs.append((lines[q[-1]], ' '.join(lines[q[-1]+1:]))); print('===== ENGLISH ====='); [print(s, '| broken =', sum(1 for _,a in pairs[:10] if not any(' '.join(a.split()) in ' '.join(c.split()) for c in chunk_text(t,strategy=s,language='en'))), '/ 10') for s in ['fixed','sentence','structure']]"
```

### Result

```text
===== ENGLISH =====
fixed | broken = 3 / 10
sentence | broken = 2 / 10
structure | broken = 0 / 10
```

---

## 2. Arabic — Broken Answer Rate

### Terminal command

```powershell
python -c "from app.ingestion.pipeline import extract_document; from app.chunking.chunker import chunk_text; t=extract_document('corpus/ar/orange-money.docx'); lines=[x.strip() for x in t.splitlines() if x.strip()]; q=[i for i,x in enumerate(lines) if x.endswith('؟')]; pairs=[(lines[i], ' '.join(lines[i+1:q[n+1]])) for n,i in enumerate(q[:-1])]; pairs.append((lines[q[-1]], ' '.join(lines[q[-1]+1:]))); print('===== ARABIC ====='); [print(s, '| broken =', sum(1 for _,a in pairs[:10] if not any(' '.join(a.split()) in ' '.join(c.split()) for c in chunk_text(t,strategy=s,language='ar'))), '/ 10') for s in ['fixed','sentence','structure']]"
```

### Result

```text
===== ARABIC =====
fixed | broken = 4 / 10
sentence | broken = 0 / 10
structure | broken = 0 / 10
```

---

## 3. English — Answer Survival

### Terminal command

```powershell
python -c "from app.ingestion.pipeline import extract_document; from app.chunking.chunker import chunk_text; t=extract_document('corpus/en/orange-money.docx'); lines=[x.strip() for x in t.splitlines() if x.strip()]; q=[i for i,x in enumerate(lines) if x.endswith('?')]; pairs=[(lines[i], ' '.join(lines[i+1:q[n+1]])) for n,i in enumerate(q[:-1])]; pairs.append((lines[q[-1]], ' '.join(lines[q[-1]+1:]))); print('===== ENGLISH: ANSWER SURVIVAL ====='); [print(s, '| survived =', sum(1 for _,a in pairs[:10] if any(' '.join(a.split()) in ' '.join(c.split()) for c in chunk_text(t,strategy=s,language='en'))), '/ 10') for s in ['fixed','sentence','structure']]"
```

### Result

```text
===== ENGLISH: ANSWER SURVIVAL =====
fixed | survived = 7 / 10
sentence | survived = 8 / 10
structure | survived = 10 / 10
```

---

## 4. Arabic — Answer Survival

### Terminal command

```powershell
python -c "from app.ingestion.pipeline import extract_document; from app.chunking.chunker import chunk_text; t=extract_document('corpus/ar/orange-money.docx'); lines=[x.strip() for x in t.splitlines() if x.strip()]; q=[i for i,x in enumerate(lines) if x.endswith('؟')]; pairs=[(lines[i], ' '.join(lines[i+1:q[n+1]])) for n,i in enumerate(q[:-1])]; pairs.append((lines[q[-1]], ' '.join(lines[q[-1]+1:]))); print('===== ARABIC: ANSWER SURVIVAL ====='); [print(s, '| survived =', sum(1 for _,a in pairs[:10] if any(' '.join(a.split()) in ' '.join(c.split()) for c in chunk_text(t,strategy=s,language='ar'))), '/ 10') for s in ['fixed','sentence','structure']]"
```

### Result

```text
===== ARABIC: ANSWER SURVIVAL =====
fixed | survived = 6 / 10
sentence | survived = 10 / 10
structure | survived = 10 / 10
```

---

## Combined Test Results

| Language | Strategy  | Broken Answer | Answer Survival |
| -------- | --------- | ------------: | --------------: |
| English  | Fixed     |    3/10 (30%) |      7/10 (70%) |
| English  | Sentence  |    2/10 (20%) |      8/10 (80%) |
| English  | Structure |     0/10 (0%) |    10/10 (100%) |
| Arabic   | Fixed     |    4/10 (40%) |      6/10 (60%) |
| Arabic   | Sentence  |     0/10 (0%) |    10/10 (100%) |
| Arabic   | Structure |     0/10 (0%) |    10/10 (100%) |

These raw test results support the comparison tables above and were generated directly from the implemented chunking strategies using the first 10 FAQ question-answer pairs in each language.
