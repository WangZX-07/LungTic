export interface TiciPatientInfo {
  patient_id: string;
  patient_name: string;
  patient_sex: string;
  patient_age: string;
}

export interface TiciStudyInfo {
  study_uid: string;
  study_date: string;
  modality: string;
  phase_count: number;
  rows: number;
  cols: number;
  slice_count: number;
  pixel_spacing: number[];
  slice_thickness: number;
}

export interface TiciPhaseInfo {
  phase: string;
  has_images: boolean;
  has_masks: boolean;
  shape?: number[];
}

export interface TiciProvenance {
  source_type: string;
  source_files_count: number;
  converter_version: string;
  conversion_date: string;
  model_version?: string;
}

export interface TiciViewerInfo {
  viewer_id: string;
  filename?: string;
  status: "ready";
  format_version: string;
  patient: TiciPatientInfo;
  study: TiciStudyInfo;
  phases: TiciPhaseInfo[];
  has_igtv: boolean;
  has_trajectory: boolean;
  provenance: TiciProvenance;
  file_size_bytes: number;
}

export interface TiciSliceResponse {
  viewer_id: string;
  phase: number;
  slice: number;
  width: number;
  height: number;
  total_slices: number;
  image_base64: string;
  mask_base64: string | null;
  has_mask: boolean;
  raw_min: number;
  raw_max: number;
  window_center: number;
  window_width: number;
}

export function getPhaseIndex(phase: TiciPhaseInfo): number {
  const value = Number(phase.phase.replace("phase_", ""));
  return Number.isFinite(value) ? value : 0;
}
