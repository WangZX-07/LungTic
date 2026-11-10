import api from "@/api";
import type { TiciSliceResponse, TiciViewerInfo } from "./types";

export async function openTiciFile(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<TiciViewerInfo> {
  const form = new FormData();
  form.append("file", file);
  const response = await api.post<TiciViewerInfo>("/tici/viewer/open", form, {
    timeout: 0,
    onUploadProgress: (event) => {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return response.data;
}

export async function loadTiciSlice(
  viewerId: string,
  phase: number,
  slice: number,
  options: {
    windowCenter?: number;
    windowWidth?: number;
    includeMask?: boolean;
  } = {},
): Promise<TiciSliceResponse> {
  const response = await api.get<TiciSliceResponse>(
    `/tici/viewer/${viewerId}/slice`,
    {
      params: {
        phase,
        slice,
        window_center: options.windowCenter,
        window_width: options.windowWidth,
        include_mask: options.includeMask ?? true,
      },
    },
  );
  return response.data;
}

export async function closeTiciFile(viewerId: string): Promise<void> {
  await api.delete(`/tici/viewer/${viewerId}`);
}
