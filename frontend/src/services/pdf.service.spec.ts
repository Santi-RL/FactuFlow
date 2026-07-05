import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import api from "@/services/api";
import pdfService from "@/services/pdf.service";

vi.mock("@/services/api", () => ({
  default: {
    get: vi.fn(),
  },
}));

const PDF_PREVIEW_URL_FALLBACK_REVOKE_MS = 5 * 60 * 1000;
const mockedApi = api as unknown as { get: Mock };
const createObjectURLMock = vi.fn(() => "blob:factuflow-preview");
const revokeObjectURLMock = vi.fn();
const originalCreateObjectURL = window.URL.createObjectURL;
const originalRevokeObjectURL = window.URL.revokeObjectURL;

describe("pdfService", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    mockedApi.get.mockResolvedValue({ data: new Uint8Array([37, 80, 68, 70]) });
    Object.defineProperty(window.URL, "createObjectURL", {
      configurable: true,
      value: createObjectURLMock,
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectURLMock,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    restoreURLMethod("createObjectURL", originalCreateObjectURL);
    restoreURLMethod("revokeObjectURL", originalRevokeObjectURL);
  });

  it("mantiene vivo el blob URL hasta que la pestaña de preview carga", async () => {
    const listeners = new Map<string, EventListener>();
    const previewWindow = buildPreviewWindow(listeners);
    const openSpy = vi.spyOn(window, "open").mockReturnValue(previewWindow);

    await pdfService.previsualizarPDF(42);

    expect(mockedApi.get).toHaveBeenCalledWith(
      "/api/pdf/comprobante/42/preview",
      { responseType: "blob" },
    );
    expect(openSpy).toHaveBeenCalledWith("blob:factuflow-preview", "_blank");
    expect(revokeObjectURLMock).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(revokeObjectURLMock).not.toHaveBeenCalled();
    expect(listeners.has("pagehide")).toBe(false);
    expect(listeners.has("unload")).toBe(false);

    listeners.get("load")?.(new Event("load"));
    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:factuflow-preview");

    vi.advanceTimersByTime(PDF_PREVIEW_URL_FALLBACK_REVOKE_MS);
    expect(revokeObjectURLMock).toHaveBeenCalledTimes(1);
  });

  it("usa un fallback largo si no puede observar la ventana de preview", async () => {
    vi.spyOn(window, "open").mockReturnValue(null);

    await pdfService.previsualizarPDF(43);

    vi.advanceTimersByTime(PDF_PREVIEW_URL_FALLBACK_REVOKE_MS - 1);
    expect(revokeObjectURLMock).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:factuflow-preview");
  });
});

function buildPreviewWindow(listeners: Map<string, EventListener>): Window {
  return {
    addEventListener: vi.fn(
      (event: string, listener: EventListenerOrEventListenerObject) => {
        if (typeof listener === "function") {
          listeners.set(event, listener);
        }
      },
    ),
  } as unknown as Window;
}

function restoreURLMethod(
  method: "createObjectURL" | "revokeObjectURL",
  original: typeof window.URL.createObjectURL | typeof window.URL.revokeObjectURL,
): void {
  if (original) {
    Object.defineProperty(window.URL, method, {
      configurable: true,
      value: original,
    });
    return;
  }

  Reflect.deleteProperty(window.URL, method);
}
