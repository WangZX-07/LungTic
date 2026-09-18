interface LungTicConnection {
  origin: string;
  pin: string;
}

interface Window {
  lungticConnection?: {
    load: () => Promise<LungTicConnection | null>;
    save: (connection: LungTicConnection) => Promise<LungTicConnection>;
  };
}
