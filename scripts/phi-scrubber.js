/**
 * PhysioWorks PHI scrubber
 *
 * Client-side, regex-based redaction modelled on the HIPAA Safe Harbor
 * identifiers (45 CFR 164.514(b)(2)) that commonly appear in clinical notes:
 * names, dates, phone/fax numbers, street addresses / ZIP codes, SSNs, MRNs.
 * Emails and URLs are also removed because they are direct identifiers.
 *
 * Replacements are monospace markdown tags, e.g. `[REDACTED_NAME]`.
 *
 * LIMITATION: regex cannot recognise every free-text name. Names are matched
 * when introduced by a title (Mr./Dr.), a label ("Patient:", "Name:"), or a
 * phrase ("named", "name is"). Always review the preview before approving.
 */
(function (root) {
  "use strict";

  var TAG = function (kind) { return "`[REDACTED_" + kind + "]`"; };

  var MONTHS = "(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)";
  var STATES = "(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)";
  var STREET_TYPES = "(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Place|Pl|Way|Terrace|Ter|Parkway|Pkwy|Highway|Hwy|Trail|Trl|Loop|Square|Sq)";

  // --- Identifier patterns (order matters; most specific first) ---------------

  // MRN / account / chart / patient-ID numbers: "MRN: 00123456", "MRN# A-12345"
  var MRN_RE = /\b(?:MRN|M\.R\.N\.?|medical\s+record(?:\s+(?:number|no\.?|#))?|chart\s*(?:number|no\.?|#)|patient\s*id|account\s*(?:number|no\.?|#)|acct\.?|FIN|encounter\s*(?:number|no\.?|#|id))\s*(?:#|no\.?|number|:|is|-)?\s*[A-Z]{0,4}[-\s]?\d[\dA-Z-]{3,}\b/gi;

  // SSN: 123-45-6789, 123 45 6789, 123456789 when labelled
  var SSN_RE = /\b\d{3}[-\s]\d{2}[-\s]\d{4}\b/g;
  var SSN_LABELLED_RE = /\b(?:SSN|SS#|social\s+security(?:\s+(?:number|no\.?|#))?)\s*(?:#|:|is|-)?\s*\d{9}\b/gi;

  // Phone / fax: (253) 555-0100, 253-555-0100, 253.555.0100, +1 253 555 0100, 555-0100
  var PHONE_RE = /(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\b\d{3})[\s.-]\d{3}[\s.-]\d{4}\b|\b\d{3}[-.]\d{4}\b/g;

  // Dates: 3/4/2024, 03-04-24, 2024-03-04, March 4, 2024, 4 March 2024, March 4th, March 2024
  var DATE_RES = [
    /\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b/g,
    /\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b/g,
    new RegExp("\\b" + MONTHS + "\\.?\\s+\\d{1,2}(?:st|nd|rd|th)?(?:,?\\s+\\d{4})?\\b", "gi"),
    new RegExp("\\b\\d{1,2}(?:st|nd|rd|th)?\\s+(?:of\\s+)?" + MONTHS + "\\.?(?:,?\\s+\\d{4})?\\b", "gi"),
    new RegExp("\\b" + MONTHS + "\\.?,?\\s+\\d{4}\\b", "gi"),
    // Labelled partial dates (DOB / DOS / DOI / surgery date) with a bare numeric value
    /\b(?:DOB|D\.O\.B\.?|DOS|DOI|date\s+of\s+(?:birth|service|injury|surgery))\s*[:\-]?\s*\d{1,2}[-/.]\d{1,2}\b/gi
  ];

  // Ages over 89 are Safe Harbor identifiers
  var AGE_OVER_89_RE = /\b(?:9\d|1[0-4]\d)(?=\s*(?:-|\s)?\s*(?:y\/?o|yo|y\.o\.|years?\s*old|yrs?\s*old))/gi;

  // Addresses
  var PO_BOX_RE = /\bP\.?\s?O\.?\s+Box\s+\d+\b/gi;
  var STREET_RE = new RegExp(
    "\\b\\d{1,6}\\s+(?:[NSEW]\\.?\\s+|(?:North|South|East|West)\\s+)?(?:[A-Za-z0-9'’.-]+\\s+){0,4}?" +
    STREET_TYPES + "\\b\\.?(?:\\s*,?\\s*(?:Apt|Apartment|Unit|Suite|Ste|#)\\.?\\s*[\\w-]+)?" +
    "(?:\\s*,\\s*[A-Z][A-Za-z.' -]+?(?:\\s*,)?\\s+" + STATES + "(?:\\s+\\d{5}(?:-\\d{4})?)?)?",
    "g"
  );
  // "Kent, WA 98032" / "WA 98032"
  var CITY_STATE_ZIP_RE = new RegExp(
    "(?:\\b[A-Z][A-Za-z.'-]+(?:\\s+[A-Z][A-Za-z.'-]+)?,\\s*)?\\b" + STATES + "\\s+\\d{5}(?:-\\d{4})?\\b",
    "g"
  );
  var ZIP_LABELLED_RE = /\b(?:zip(?:\s*code)?|postal\s*code)\s*[:\-]?\s*\d{5}(?:-\d{4})?\b/gi;

  // Other direct identifiers
  var EMAIL_RE = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
  var URL_RE = /\b(?:https?:\/\/|www\.)[^\s<>"')]+/gi;

  // --- Names -----------------------------------------------------------------

  var NAME_WORD = "(?:[A-Za-z]\\.|[A-Za-z][A-Za-z'’-]+)";
  var NAME_TOKEN_RE = /^[A-Z][A-Za-z'’-]*\.?$|^[A-Z]\.?$/;
  var NAME_STOP = /^(?:The|A|An|And|Or|Of|With|Who|Is|Was|Presents?|Presented|Reports?|Reported|Referred|Complains?|Denies|States?|Stated|Has|Had|Status|Post|Pre|Following|Diagnosis|Dx|History|Hx|Evaluation|Eval|Initial|Follow|Seen|Today|Left|Right|Bilateral|Male|Female|Patient|Pt|MRN|DOB)$/;

  // Title + name: "Mr. John Smith", "Dr Alvarez", "Mrs. O'Neil"
  var TITLE_RE = new RegExp("\\b(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof|Professor)\\.?\\s+((?:" + NAME_WORD + "\\s+){0,2}" + NAME_WORD + ")", "g");

  // Label + name: "Patient: Jane Doe", "Name - Doe, Jane", "Pt name is ...", "Referred by: ..."
  var LABEL_RE = new RegExp(
    "\\b((?:patient(?:'s|’s)?(?:\\s+name)?|pt(?:\\.|'s|’s)?(?:\\s+name)?|name|client|member|guardian|spouse|wife|husband|mother|father|parent|caregiver|emergency\\s+contact|referred\\s+by|referring\\s+(?:provider|physician|doctor)|PCP|physician|provider|surgeon|therapist|PT|signed(?:\\s+by)?|re)\\s*(?:name\\s*)?(?::|-|–|—|\\bis\\b)\\s*)(" + NAME_WORD + "(?:,?[ \\t]+" + NAME_WORD + "){0,3})",
    "gi"
  );

  // Phrase: "named John Smith", "my name is Jane", "known as"
  var NAMED_RE = new RegExp("\\b((?:is\\s+|was\\s+)?named\\s+|(?:my|his|her|their)\\s+name\\s+is\\s+|goes\\s+by\\s+|known\\s+as\\s+)(" + NAME_WORD + "(?:[ \\t]+" + NAME_WORD + "){0,2})", "gi");

  // Possessive after Mr/Mrs etc. is handled by TITLE_RE; "Smith's" keeps the 's.

  /**
   * Consume only the leading words that look like proper names (capitalised,
   * not a stop-word). Returns { name: <consumed text>, rest: <untouched text> }.
   */
  function splitName(raw, maxWords) {
    var parts = raw.match(/\S+\s*/g) || [];
    var consumed = 0;
    var i;
    for (i = 0; i < parts.length && consumed < maxWords; i++) {
      var word = parts[i].replace(/[\s,]+$/, "").replace(/(?:'s|’s)$/, "");
      if (!NAME_TOKEN_RE.test(word) || NAME_STOP.test(word)) break;
      consumed++;
    }
    if (!consumed) return null;
    var name = parts.slice(0, consumed).join("");
    var trailing = name.match(/[\s,]*$/)[0];
    return { name: name.slice(0, name.length - trailing.length), rest: trailing + parts.slice(consumed).join("") };
  }

  function redactNames(text) {
    var tag = TAG("NAME");

    text = text.replace(TITLE_RE, function (full, nameRaw) {
      var s = splitName(nameRaw, 3);
      if (!s) return full;
      var prefix = full.slice(0, full.length - nameRaw.length);
      return prefix + tag + s.rest;
    });

    text = text.replace(LABEL_RE, function (full, label, nameRaw) {
      var s = splitName(nameRaw, 4);
      if (!s) return full;
      return label + tag + s.rest;
    });

    text = text.replace(NAMED_RE, function (full, label, nameRaw) {
      var s = splitName(nameRaw, 3);
      if (!s) return full;
      return label + tag + s.rest;
    });

    // Collapse adjacent name tags ("`[REDACTED_NAME]` `[REDACTED_NAME]`")
    return text.replace(/(`\[REDACTED_NAME\]`)(?:\s*,?\s*`\[REDACTED_NAME\]`)+/g, "$1");
  }

  // --- Public API ------------------------------------------------------------

  function sanitizeClinicalText(text) {
    if (text === null || text === undefined) return "";
    var out = String(text);
    if (!out.trim()) return "";

    out = out.replace(MRN_RE, TAG("MRN"));
    out = out.replace(SSN_LABELLED_RE, TAG("SSN"));
    out = out.replace(SSN_RE, TAG("SSN"));
    out = out.replace(EMAIL_RE, TAG("EMAIL"));
    out = out.replace(URL_RE, TAG("URL"));
    out = out.replace(PHONE_RE, TAG("PHONE"));
    DATE_RES.forEach(function (re) { out = out.replace(re, TAG("DATE")); });
    out = out.replace(AGE_OVER_89_RE, TAG("AGE"));
    out = out.replace(PO_BOX_RE, TAG("ADDRESS"));
    out = out.replace(STREET_RE, TAG("ADDRESS"));
    out = out.replace(CITY_STATE_ZIP_RE, TAG("ADDRESS"));
    out = out.replace(ZIP_LABELLED_RE, TAG("ADDRESS"));
    out = redactNames(out);

    return out;
  }

  var api = { sanitizeClinicalText: sanitizeClinicalText };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.sanitizeClinicalText = sanitizeClinicalText;
  root.PhysioPhiScrubber = api;
})(typeof window !== "undefined" ? window : globalThis);
