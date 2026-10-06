/*
 * Free-text intake flow helpers (D047, CONTRACTS_V0_3_CONTEXTUAL §25).
 * Mirrors signal_diag.app.intake_flow.assemble_intake_submission; both run the
 * shared table tests/app/fixtures/intake_assembly_cases.json.
 * A null field means "not confirmed by the user".
 */

const INTAKE_DIAGNOSIS_QUESTION = "Why does this signal sound distorted?";
const INTAKE_CONTEXT_ORIGIN = "intake_confirmed";
const INTAKE_MAX_FILES = 2;
const INTAKE_MODES = ["single_signal", "paired_reference", "nominal_single_tone"];

function intakeInvalid(message) {
  const error = new Error(message);
  error.code = "invalid_request";
  return error;
}

function intakeCheckHz(value) {
  if (value === null || value === undefined) return null;
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    throw intakeInvalid("nominal_fundamental_hz must be a finite positive number");
  }
  return value;
}

function assembleIntakeSubmission(selection, filenames, testFile) {
  const names = Array.from(filenames);
  if (names.length === 0 || names.length > INTAKE_MAX_FILES) {
    throw intakeInvalid(`intake accepts 1 to ${INTAKE_MAX_FILES} WAV files`);
  }
  if (new Set(names).size !== names.length) {
    throw intakeInvalid("intake filenames must be distinct");
  }
  if (!names.includes(testFile)) {
    throw intakeInvalid("test_file must be one of the uploaded files");
  }
  const mode = selection.mode ?? null;
  const reference = selection.reference_file ?? null;
  const kind = selection.stimulus_kind ?? null;
  if (mode !== null && !INTAKE_MODES.includes(mode)) {
    throw intakeInvalid(`unsupported contextual mode: ${mode}`);
  }
  if (reference !== null) {
    if (typeof reference !== "string" || !names.includes(reference)) {
      throw intakeInvalid("reference_file must be one of the uploaded files");
    }
    if (reference === testFile) {
      throw intakeInvalid("reference_file must not be the test file");
    }
  }
  if (kind !== null && kind !== "single_tone") {
    throw intakeInvalid("stimulus_kind must be single_tone when confirmed");
  }
  const hz = intakeCheckHz(selection.nominal_fundamental_hz ?? null);
  const single = (downgradedFrom, unconfirmed) => ({
    mode: "single_signal",
    reference_file: null,
    nominal_fundamental_hz: null,
    stimulus_kind: null,
    downgraded_from: downgradedFrom,
    unconfirmed_fields: unconfirmed,
  });

  if (mode === null) return single(null, ["mode"]);
  if (mode === "paired_reference") {
    if (reference === null) return single("paired_reference", ["reference_file"]);
    const both = hz !== null && kind !== null;
    return {
      mode: "paired_reference",
      reference_file: reference,
      nominal_fundamental_hz: both ? hz : null,
      stimulus_kind: both ? kind : null,
      downgraded_from: null,
      unconfirmed_fields: [],
    };
  }
  if (mode === "nominal_single_tone") {
    const missing = [];
    if (hz === null) missing.push("nominal_fundamental_hz");
    if (kind === null) missing.push("stimulus_kind");
    if (missing.length > 0) return single("nominal_single_tone", missing);
    return {
      mode: "nominal_single_tone",
      reference_file: null,
      nominal_fundamental_hz: hz,
      stimulus_kind: kind,
      downgraded_from: null,
      unconfirmed_fields: [],
    };
  }
  return single(null, []);
}

function intakeDowngradeMessage(assembly) {
  const unconfirmed = assembly.unconfirmed_fields;
  if (assembly.downgraded_from === null && unconfirmed.length === 1 && unconfirmed[0] === "mode") {
    return "mode is not confirmed; diagnosing as single_signal";
  }
  if (assembly.downgraded_from === null) return null;
  const verb = unconfirmed.length === 1 ? "is" : "are";
  return (
    `${assembly.downgraded_from} needs ${unconfirmed.join(" and ")}, which ${verb} ` +
    "not confirmed; diagnosing as single_signal"
  );
}

/** Sample rate from a RIFF/WAVE header buffer; null when absent. Reads metadata only. */
function wavHeaderSampleRate(buffer) {
  const view = new DataView(buffer);
  const tag = (offset) =>
    String.fromCharCode(
      view.getUint8(offset),
      view.getUint8(offset + 1),
      view.getUint8(offset + 2),
      view.getUint8(offset + 3),
    );
  if (view.byteLength < 12 || tag(0) !== "RIFF" || tag(8) !== "WAVE") return null;
  let offset = 12;
  while (offset + 8 <= view.byteLength) {
    const size = view.getUint32(offset + 4, true);
    if (tag(offset) === "fmt ") {
      if (size < 8 || offset + 16 > view.byteLength) return null;
      const rate = view.getUint32(offset + 12, true);
      return rate > 0 ? rate : null;
    }
    offset += 8 + size + (size % 2);
  }
  return null;
}

/** JSON body for POST /api/v1/intake/draft: text and file metadata only, never audio. */
function buildDraftRequestBody(text, filenames, testFile, sampleRates) {
  const rates = Array.from(sampleRates);
  return {
    text,
    filenames: Array.from(filenames),
    test_file: testFile,
    sample_rates_hz: rates.every((rate) => typeof rate === "number") ? rates : [],
  };
}

/** Multipart body for POST /api/v1/contextual-runs/wav from a confirmed assembly. */
function buildIntakeDiagnoseForm(assembly, filesByName, testFile, channel) {
  const body = new FormData();
  body.append("test_file", filesByName[testFile], testFile);
  body.append("mode", assembly.mode);
  body.append("user_request", INTAKE_DIAGNOSIS_QUESTION);
  body.append("channel", channel);
  body.append("context_origin", INTAKE_CONTEXT_ORIGIN);
  if (assembly.nominal_fundamental_hz !== null) {
    body.append("nominal_fundamental_hz", String(assembly.nominal_fundamental_hz));
  }
  if (assembly.stimulus_kind !== null) {
    body.append("stimulus_kind", assembly.stimulus_kind);
  }
  if (assembly.reference_file !== null) {
    body.append(
      "reference_file",
      filesByName[assembly.reference_file],
      assembly.reference_file,
    );
  }
  return body;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    INTAKE_CONTEXT_ORIGIN,
    INTAKE_DIAGNOSIS_QUESTION,
    assembleIntakeSubmission,
    buildDraftRequestBody,
    buildIntakeDiagnoseForm,
    intakeDowngradeMessage,
    wavHeaderSampleRate,
  };
}
