/**
 * PhysioWorks PHI Scrubber
 *
 * Client-side, regex-based redaction modeled on the HIPAA Safe Harbor
 * identifiers (45 CFR 164.514(b)(2)) that commonly appear in clinical notes:
 * names, dates, demographics/age/gender shorthand, phone/fax numbers,
 * street addresses / ZIP codes, SSNs, MRNs.
 *
 * Replacements are monospace markdown tags, e.g. `[REDACTED_NAME]`.
 */
(function (root) {
  "use strict";

  var TAG = function (kind) { return "`[REDACTED_" + kind + "]`"; };

  var MONTHS = "(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)";
  var STATES = "(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)";
  var STREET_TYPES = "(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Place|Pl|Way|Terrace|Ter|Parkway|Pkwy|Highway|Hwy|Trail|Trl|Loop|Square|Sq)";

  // --- Identifier patterns (order matters; most specific first) ---------------

  // Demographic & Clinical Shorthand: "58yo M", "58 y.o. male", "42 yo female", "67 y/o F"
  var AGE_GENDER_RE = /\b\d{1,3}\s*(?:yo|y\.o\.|y\/o|yr|year|years)\s*(?:old)?\s*(?:m|f|male|female)\b/gi;

  // Standalone Age: "58yo", "58 y/o", "58 years old"
  var AGE_RE = /\b\d{1,3}\s*(?:yo|y\.o\.|y\/o|years\s+old)\b/gi;

  // Patient intro phrases
  var PT_INTRO_RE = /\b(?:patient|pt)\s+is\s+an?\s+/gi;

  // Labelled demographics
  var DOB_RE = /\b(?:dob|d\.o\.b\.|date\s+of\s+birth)\s*[:\-]?\s*[^\n\r,;]+/gi;
  var GENDER_LABEL_RE = /\b(?:gender|sex)\s*[:\-]?\s*(?:male|female|m|f|non-binary|other)\b/gi;

  // MRN / account / chart / patient-ID numbers: "MRN: 00123456", "MRN# A-12345"
  var MRN_RE = /\b(?:MRN|M\.R\.N\.?|medical\s+record(?:\s+(?:number|no\.?|#))?|chart\s*(?:number|no\.?|#)|patient\s*id|account\s*(?:number|no\.?|#)|acct\.?|FIN|encounter\s*(?:number|no\.?|#|id))\s*(?:#|no\.?|number|:|is|-)?\s*[A-Z]{0,4}[-\s]?\d[\dA-Z-]{3,}\b/gi;

  // SSN: 123-45-6789, 123 45 6789, 123456789 when labelled
  var SSN_RE = /\b\d{3}[-\s]\d{2}[-\s]\d{4}\b/g;
  var SSN_LABELLED_RE = /\b(?:SSN|SS#|social\s+security(?:\s+(?:number|no\.?|#))?)\s*(?:#|:|is|-)?\s*\d{9}\b/gi;

  // Phone / fax: (253) 555-0100, 253-555-0100, 253.555.0100, +1 253 555 0100, 555-0100
  var PHONE_RE = /(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\b\d{3})[\s.-]\d{3}[\s.-]\d{4}\b|\b\d{3}[-.]\d{4}\b/g;

  // Email addresses
  var EMAIL_RE = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g;

  // Dates: 3/4/2024, 03-04-24, 2024-03-04, March 4, 2024, 4 March 2024, March 4th, March 2024
  var DATE_RES = [
    /\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b/g,
    /\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b/g,
    new RegExp("\\b" + MONTHS + "\\.?\\s+\\d{1,2}(?:st|nd|rd|th)?(?:,?\\s+\\d{4})?\\b", "gi"),
    new RegExp("\\b\\d{1,2}\\s+" + MONTHS + "\\.?\\s+\\d{4}\\b", "gi"),
    new RegExp("\\b" + MONTHS + "\\s+\\d{4}\\b", "gi")
  ];

  // ZIP codes: 98383, 98032, 98383-1234 (labelled or 5+4)
  var ZIP_RE = /\b\d{5}-\d{4}\b|\b(?:zip(?:\s*code)?|postal(?:\s*code)?)\s*[:#-]?\s*\d{5}\b/gi;

  // Street addresses: "123 Main St", "10404 Silverdale Way NW"
  var ADDRESS_RE = new RegExp("\\b\\d{1,6}\\s+[A-Za-z0-9.\\s]{1,30}?\\s+" + STREET_TYPES + "\\b(?:\\s+(?:Suite|Ste|Apt|Unit|#)\\s*[A-Za-z0-9-]+)?", "gi");

  // Labelled patient names: "Patient: John Doe", "Name: Jane Smith", "Pt: Bob"
  var LABELLED_NAME_RE = /\b(?:patient\s*name|pt\s*name|patient|pt|client|eval\s+for|named|name\s*is)\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})/gi;

  // Title-prefixed names: "Mr. Doe", "Ms. Smith", "Dr. Kovach"
  var TITLED_NAME_RE = /\b(?:Mr\.|Mrs\.|Ms\.|Miss|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b/g;

  function sanitize(text) {
    if (!text) return "";
    var out = String(text);

    // 1. Structural identifiers & labels
    out = out.replace(SSN_LABELLED_RE, TAG("SSN"));
    out = out.replace(SSN_RE, TAG("SSN"));
    out = out.replace(MRN_RE, TAG("MRN"));
    out = out.replace(DOB_RE, TAG("DOB"));
    out = out.replace(GENDER_LABEL_RE, TAG("GENDER"));

    // 2. Clinical demographics shorthand
    out = out.replace(PT_INTRO_RE, "Individual is ");
    out = out.replace(AGE_GENDER_RE, TAG("AGE_GENDER"));
    out = out.replace(AGE_RE, TAG("AGE"));

    // 3. Contact & address info
    out = out.replace(EMAIL_RE, TAG("EMAIL"));
    out = out.replace(PHONE_RE, TAG("PHONE"));
    out = out.replace(ZIP_RE, TAG("ZIP"));
    out = out.replace(ADDRESS_RE, TAG("ADDRESS"));

    // 4. Dates
    for (var i = 0; i < DATE_RES.length; i++) {
      out = out.replace(DATE_RES[i], TAG("DATE"));
    }

    // 5. Patient names
    out = out.replace(LABELLED_NAME_RE, function (match, p1) {
      return match.replace(p1, TAG("NAME"));
    });
    out = out.replace(TITLED_NAME_RE, function (match, p1) {
      return match.replace(p1, TAG("NAME"));
    });

    return out;
  }

  var PhysioPhiScrubber = {
    sanitize: sanitize,
    TAG: TAG
  };

  root.PhysioPhiScrubber = PhysioPhiScrubber;
  root.sanitizeClinicalText = sanitize;
  root.scrubPHI = sanitize;
})(typeof window !== "undefined" ? window : this);
