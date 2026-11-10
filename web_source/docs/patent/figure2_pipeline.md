```mermaid
flowchart TD
    START(["<b>START</b><br/>DICOM / NIfTI / .tiCi Upload"]):::start
    
    START --> P1_LABEL

    subgraph PHASE1["<b>PHASE 1 — 创建 .tiCi (mode: w)</b>"]
        direction TB
        P1_LABEL[" "]:::hidden
        P1["<b>Create .tiCi File</b><br/><br/>write_metadata()<br/>→ /patient + /study<br/><br/>write_phase_images()<br/>→ /phases/*/images [gzip-4]<br/><br/>write_provenance()<br/>→ /provenance"]:::phase1
    end

    PHASE1 --> P2_LABEL

    subgraph PHASE2["<b>PHASE 2 — 追加分割掩膜 (mode: a)</b>"]
        direction TB
        P2_LABEL[" "]:::hidden
        P2_SEG["<b>U-Net Segmentation</b><br/>Per-slice binary mask generation"]:::seg
        P2_SEG --> P2_APPEND["append_phase_masks()<br/>→ /phases/0..N/masks [lzf]"]:::append1
    end

    P2_APPEND --> P3_LABEL

    subgraph PHASE3["<b>PHASE 3 — 追加 IGTV 靶区 (mode: a)</b>"]
        direction TB
        P3_LABEL[" "]:::hidden
        P3_RECON["<b>IGTV Reconstruction</b><br/>Marching Cubes + Volume Calculation"]:::igtv
        P3_RECON --> P3_APPEND["write_igtv()<br/>→ /igtv/mask + /igtv/mesh + @volume_cc"]:::append2
    end

    P3_APPEND --> P4_LABEL

    subgraph PHASE4["<b>PHASE 4 — 追加轨迹预测 (mode: a)</b>"]
        direction TB
        P4_LABEL[" "]:::hidden
        P4_PRED["<b>LSTM Trajectory Prediction</b><br/>BiLSTM + TCN"]:::traj
        P4_PRED --> P4_APPEND["write_trajectory()<br/>→ /trajectory/centroids + observed + predicted"]:::append3
    end

    P4_APPEND --> FINAL

    FINAL(["<b>Single .tiCi File</b><br/>images + masks + IGTV + trajectory<br/><br/>Download / Exchange / Archive"]):::success

    classDef start fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    classDef phase1 fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    classDef seg fill:#FFF3E0,stroke:#E65100,stroke-width:2px,color:#BF360C
    classDef append1 fill:#FFF8E1,stroke:#F9A825,stroke-width:1px,color:#795548
    classDef igtv fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px,color:#4A148C
    classDef append2 fill:#FCE4EC,stroke:#C62828,stroke-width:1px,color:#B71C1C
    classDef traj fill:#E0F2F1,stroke:#00695C,stroke-width:2px,color:#004D40
    classDef append3 fill:#E0F2F1,stroke:#00695C,stroke-width:1px,color:#004D40
    classDef success fill:#C8E6C9,stroke:#1B5E20,stroke-width:3px,color:#1B5E20
    classDef hidden fill:none,stroke:none,color:transparent

    style PHASE1 fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    style PHASE2 fill:#FFF8E1,stroke:#F57F17
    style PHASE3 fill:#FCE4EC,stroke:#C62828
    style PHASE4 fill:#E0F2F1,stroke:#00695C
