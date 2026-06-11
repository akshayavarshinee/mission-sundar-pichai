"""Curated, demo-sized customs-law knowledge base + hard veto facts.

This is a deliberately small slice of real US import/export rules — enough to
*ground* the Customs Auditor's diagnoses and to give memory tier ① a genuine
**veto** over learned experience. It is not a complete legal corpus.

Sources referenced (paraphrased for the demo, not verbatim legal text):
  * USITC Harmonized Tariff Schedule (HTS) headings
  * CBP CROSS (Customs Rulings Online Search System) classification rulings
  * Foreign Trade Regulations (FTR) §30.37 — EEI filing exemptions
"""

from __future__ import annotations

from clearport.schemas import NormalizedErrorType

# ── ① grounding chunks (embedded + semantically retrieved as citations) ──────
LAW_CHUNKS: list[dict] = [
    {
        "id": "hts-8302-49",
        "source": "HTS",
        "ref": "8302.49",
        "hs_chapter": "83",
        "text": (
            "HTS 8302.49 covers base metal mountings, fittings and similar articles, "
            "including keychains and key rings of base metal such as brass."
        ),
    },
    {
        "id": "hts-6109-10",
        "source": "HTS",
        "ref": "6109.10",
        "hs_chapter": "61",
        "text": (
            "HTS 6109.10 covers T-shirts, singlets and other vests, knitted or "
            "crocheted, of cotton."
        ),
    },
    {
        "id": "hts-6214-40",
        "source": "HTS",
        "ref": "6214.40",
        "hs_chapter": "62",
        "text": (
            "HTS 6214.40 covers shawls, scarves, mufflers, mantillas, veils and the "
            "like, of artificial fibres / other textile materials."
        ),
    },
    {
        "id": "hts-0904-11",
        "source": "HTS",
        "ref": "0904.11",
        "hs_chapter": "09",
        "text": (
            "HTS 0904.11 covers pepper of the genus Piper, neither crushed nor "
            "ground. Food/plant products may be subject to quarantine controls."
        ),
    },
    {
        "id": "hts-4602-19",
        "source": "HTS",
        "ref": "4602.19",
        "hs_chapter": "46",
        "text": (
            "HTS 4602.19 covers basketwork, wickerwork and other articles made "
            "directly to shape from plaiting materials (other than of bamboo/rattan)."
        ),
    },
    {
        "id": "cross-keychain-8302",
        "source": "CROSS",
        "ref": "NY-EXAMPLE-KEYCHAIN",
        "hs_chapter": "83",
        "text": (
            "CBP CROSS rulings classify decorative brass keychains/key rings as base "
            "metal articles under heading 8302, not as jewellery."
        ),
    },
    {
        "id": "ftr-30-37-a",
        "source": "EEI",
        "ref": "FTR 30.37(a)",
        "hs_chapter": "*",
        "text": (
            "FTR §30.37(a): EEI filing is not required when the value of goods under "
            "a single Schedule B/HTS number, shipped to one consignee, is $2,500 or "
            "less. At or above $2,500 per line, EEI must be filed (an AES ITN is "
            "required); claiming NOEEI 30.37(a) is not permitted."
        ),
    },
    {
        "id": "cbp-restricted-comments",
        "source": "EEI",
        "ref": "CBP-RESTRICTED",
        "hs_chapter": "*",
        "text": (
            "When a customs declaration marks goods as restricted (quarantine, "
            "sanitary/phytosanitary, or other), an explanatory restriction comment "
            "describing the restriction and any permit is required."
        ),
    },
    {
        "id": "cbp-certify-signer",
        "source": "EEI",
        "ref": "CBP-CERTIFY",
        "hs_chapter": "*",
        "text": (
            "If the shipper certifies the customs declaration (customs_certify=true), "
            "the name of the certifying signer is required."
        ),
    },
]

# ── ① hard veto facts (rule-checked, override learned experience) ────────────
LAW_FACTS: dict[NormalizedErrorType, dict] = {
    NormalizedErrorType.EEI_THRESHOLD_MISMATCH: {
        "source": "EEI",
        "ref": "FTR 30.37(a)",
        "text": (
            "At or above $2,500 per HTS line, NOEEI 30.37(a) is invalid; a proper "
            "EEI/AES filing is required."
        ),
    },
    NormalizedErrorType.HS_INVALID: {
        "source": "HTS",
        "ref": "GRI/HTS-format",
        "text": "An HTS tariff number must be a valid 6- or 10-digit code.",
    },
    NormalizedErrorType.RESTRICTION_COMMENTS_MISSING: {
        "source": "CBP",
        "ref": "CBP-RESTRICTED",
        "text": "Restricted goods require an explanatory restriction comment.",
    },
    NormalizedErrorType.SIGNER_MISSING: {
        "source": "CBP",
        "ref": "CBP-CERTIFY",
        "text": "A certified declaration requires a named signer.",
    },
}


def law_fact_for(error_type: NormalizedErrorType) -> dict | None:
    return LAW_FACTS.get(error_type)


# ── ① taxonomy → cited authority ─────────────────────────────────────────────
# Every recoverable rejection class is mapped to the recognized authority that
# governs it, so each diagnosis can name its legal basis (provenance, not the
# agent's reasoning). Authority families are paraphrased for the demo — not
# verbatim legal text. UNKNOWN is intentionally absent (no rule to cite).
ERROR_AUTHORITIES: dict[NormalizedErrorType, dict] = {
    NormalizedErrorType.HS_INVALID: {
        "label": "Invalid HS code",
        "regime": "Tariff classification",
        "authority": "HTS GRI 1 · CBP CROSS",
        "short": "HTS GRI 1",
        "basis": (
            "Goods are classified under the HTS General Rules of Interpretation; the "
            "tariff number must be a valid 6- or 10-digit HTS code, with CBP CROSS "
            "rulings as the binding precedent source."
        ),
    },
    NormalizedErrorType.EEI_THRESHOLD_MISMATCH: {
        "label": "EEI threshold",
        "regime": "Export filing (EEI/AES)",
        "authority": "FTR 15 CFR §30.37(a)",
        "short": "FTR §30.37(a)",
        "basis": (
            "EEI is exempt only when the value per Schedule B/HTS line to one consignee "
            "is $2,500 or less; at or above $2,500 an AES ITN is required and claiming "
            "NOEEI 30.37(a) is invalid."
        ),
    },
    NormalizedErrorType.RESTRICTION_COMMENTS_MISSING: {
        "label": "Missing restriction note",
        "regime": "Restricted merchandise",
        "authority": "19 CFR Part 12",
        "short": "19 CFR Pt 12",
        "basis": (
            "Special classes of merchandise (quarantine, sanitary/phytosanitary, and "
            "other restricted goods) require an explanatory restriction comment and any "
            "governing permit."
        ),
    },
    NormalizedErrorType.SIGNER_MISSING: {
        "label": "Unsigned certification",
        "regime": "Declaration certification",
        "authority": "19 CFR §141.19",
        "short": "19 CFR §141.19",
        "basis": (
            "A certified customs declaration must name the certifying party; a "
            "certification with no signer is invalid."
        ),
    },
    NormalizedErrorType.CONTENTS_EXPLANATION_MISSING: {
        "label": "Missing contents detail",
        "regime": "Declaration contents",
        "authority": "UPU CN22/CN23",
        "short": "UPU CN22/23",
        "basis": (
            "A customs declaration must carry an accurate description of contents; an "
            "'other' contents type requires an explicit explanation."
        ),
    },
    NormalizedErrorType.ZERO_VALUE: {
        "label": "Non-positive value",
        "regime": "Customs valuation",
        "authority": "19 CFR §152.103",
        "short": "19 CFR §152.103",
        "basis": (
            "Customs value is the transaction value (the price actually paid); a "
            "non-positive line value, quantity, or weight cannot be a valid declared "
            "value."
        ),
    },
    NormalizedErrorType.OVERLAY_SCHEMA_DRIFT: {
        "label": "Registry schema drift",
        "regime": "Gateway schema drift",
        "authority": "Destination registry schema",
        "short": "Registry schema",
        "basis": (
            "The destination registry changed a validation rule; a previously accepted "
            "field no longer satisfies the current schema. Operational, not a single "
            "legal citation."
        ),
    },
}


def authority_for(error_type: NormalizedErrorType) -> dict | None:
    return ERROR_AUTHORITIES.get(error_type)
