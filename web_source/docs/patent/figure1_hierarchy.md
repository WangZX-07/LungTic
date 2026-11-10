```mermaid
graph TB
    subgraph root[".tiCi File (HDF5 Container)<br/>MAGIC: \x89TICI\r\n\x1a\n / VERSION: 1.0"]
        direction TB
        
        subgraph patient["/patient"]
            p1["@patient_id"]
            p2["@patient_name"]
            p3["@patient_sex"]
            p4["@patient_age"]
        end
        
        subgraph study["/study"]
            s1["@study_uid"]
            s2["@study_date"]
            s3["@modality"]
            s4["@phase_count"]
            s5["@rows / @cols"]
            s6["@pixel_spacing"]
            s7["@slice_thickness"]
        end
        
        subgraph provenance["/provenance"]
            pr1["@source_type"]
            pr2["@files_count"]
            pr3["@converter_version"]
            pr4["@conversion_date"]
        end
        
        subgraph phases["/phases (N groups)"]
            subgraph p0["phase_0/"]
                p0_img["images<br/>(Z,H,W) float32<br/>[gzip level=4]"]
                p0_msk["masks<br/>(Z,H,W) uint8<br/>[lzf] (optional)"]
            end
            subgraph p1["phase_1/"]
                p1_img["images<br/>(Z,H,W) float32<br/>[gzip level=4]"]
                p1_msk["masks<br/>(Z,H,W) uint8<br/>[lzf] (optional)"]
            end
            subgraph pN["phase_N/"]
                pN_node["images + masks ..."]
            end
        end
        
        subgraph igtv["/igtv"]
            i1["@volume_cc (Float)"]
            i2["@method (String)"]
            i3["mask (Z,Y,X) uint8 [lzf]"]
            i4["mesh (OBJ text)"]
        end
        
        subgraph trajectory["/trajectory"]
            t1["@prediction_model"]
            t2["centroids (N,3) float32"]
            t3["observed (7,3) float32"]
            t4["predicted (3,3) float32"]
        end
    end
    
    style root fill:#E8EAF6,stroke:#283593,stroke-width:2px
    style patient fill:#E3F2FD,stroke:#1565C0
    style study fill:#E3F2FD,stroke:#1565C0
    style provenance fill:#FFF3E0,stroke:#E65100
    style phases fill:#E8F5E9,stroke:#2E7D32
    style p0 fill:#C8E6C9,stroke:#43A047
    style p1 fill:#C8E6C9,stroke:#43A047
    style pN fill:#C8E6C9,stroke:#43A047
    style igtv fill:#FCE4EC,stroke:#C62828
    style trajectory fill:#F3E5F5,stroke:#6A1B9A
    style p0_img fill:#A5D6A7,stroke:#388E3C
    style p0_msk fill:#A5D6A7,stroke:#388E3C
    style p1_img fill:#A5D6A7,stroke:#388E3C
    style p1_msk fill:#A5D6A7,stroke:#388E3C
    style pN_node fill:#A5D6A7,stroke:#388E3C
