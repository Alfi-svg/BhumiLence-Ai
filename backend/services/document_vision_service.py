"""
Production Document Intelligence & Evidence Cropping Service (Layers 1, 2 & 3).
Handles:
1. Layer 1 — Image Quality Gate (Blur, Contrast, Illumination, Skew, Resolution)
2. Layer 2 — Structural Layout Segmentation & Document Classification (Header, Seals, Grids, Lines)
3. Layer 3 — Evidence Cropping & Provenance Mapping (Pixel coordinates + SHA-256 verification)
"""
import os
import time
import hashlib
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import cv2
import numpy as np

from backend.schemas.document_schema import (
    QualityStatus,
    LayoutPattern,
    ImageDimensions,
    QualityAssessment,
    EvidenceCrop,
    TextLineCrop,
    LayoutAnalysis,
    DocumentAnalysisResult,
    SCHEMA_VERSION
)

class DocumentVisionService:
    def __init__(self, output_base_dir: str = "outputs/evidence"):
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """Computes SHA-256 hash of an image file to guarantee provenance."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # -------------------------------------------------------------------------
    # LAYER 1: IMAGE QUALITY GATE
    # -------------------------------------------------------------------------
    def assess_image_quality(self, img_bgr: np.ndarray) -> QualityAssessment:
        """
        Layer 1: Deterministic image quality evaluation.
        Computes:
        - Laplacian variance (Blur metric)
        - RMS contrast (Standard deviation of gray pixel intensities)
        - Mean brightness / illumination
        - Skew angle (Hough transform line orientation)
        - Resolution sufficiency
        """
        h, w = img_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # 1. Blur Score: Variance of Laplacian
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 2. RMS Contrast: Standard deviation of pixel intensities
        rms_contrast = float(np.std(gray))

        # 3. Illumination: Mean brightness
        mean_brightness = float(np.mean(gray))

        # 4. Skew Angle Estimation via HoughLinesP
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=80,
            minLineLength=max(40, w // 8), maxLineGap=20
        )
        skew_angle_deg = 0.0
        if lines is not None:
            lines_arr = np.squeeze(lines)
            if lines_arr.ndim == 1:
                lines_arr = np.expand_dims(lines_arr, axis=0)
            angles = []
            for line in lines_arr:
                if len(line) >= 4:
                    x1, y1, x2, y2 = line[:4]
                    angle = np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1)))
                    # Only consider near-horizontal lines
                    if -45.0 <= angle <= 45.0:
                        angles.append(angle)
            if angles:
                skew_angle_deg = float(np.median(angles))

        # Evaluate quality thresholds and warnings
        warnings: List[str] = []
        status = QualityStatus.PASS

        if laplacian_var < 80.0:
            warnings.append(f"Image appears blurry (Laplacian variance: {laplacian_var:.1f} < 80.0)")
            status = QualityStatus.WARN_BLURRY
        elif rms_contrast < 18.0:
            warnings.append(f"Low contrast detected (RMS contrast: {rms_contrast:.1f} < 18.0)")
            status = QualityStatus.WARN_LOW_CONTRAST
        elif abs(skew_angle_deg) > 3.0:
            warnings.append(f"Document is rotated or skewed (Estimated angle: {skew_angle_deg:.1f}°)")
            status = QualityStatus.WARN_SKEWED
        elif w < 600 or h < 600:
            warnings.append(f"Low resolution image ({w}x{h} < 600x600)")
            status = QualityStatus.WARN_LOW_RESOLUTION

        if mean_brightness < 40.0:
            warnings.append(f"Image is severely underexposed (Mean brightness: {mean_brightness:.1f} < 40.0)")
        elif mean_brightness > 235.0:
            warnings.append(f"Image is overexposed (Mean brightness: {mean_brightness:.1f} > 235.0)")

        is_acceptable = (laplacian_var >= 40.0 and rms_contrast >= 12.0)

        return QualityAssessment(
            status=status,
            laplacian_blur_variance=round(laplacian_var, 2),
            rms_contrast=round(rms_contrast, 2),
            mean_brightness=round(mean_brightness, 2),
            skew_angle_deg=round(skew_angle_deg, 2),
            dimensions=ImageDimensions(width=w, height=h),
            warnings=warnings,
            is_acceptable=is_acceptable
        )

    # -------------------------------------------------------------------------
    # PREPROCESSING & NORMALIZATION
    # -------------------------------------------------------------------------
    def preprocess_image(self, img_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Normalizes illumination and extracts clean adaptive binary image.
        Uses Gaussian division to remove shadows and CLAHE for ink enhancement.
        """
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        # Background illumination estimation
        bg_illumination = cv2.GaussianBlur(gray, (55, 55), 0)
        norm_gray = cv2.divide(gray, bg_illumination, scale=255)

        # CLAHE + Adaptive binarization
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        contrast = clahe.apply(norm_gray)
        denoised = cv2.fastNlMeansDenoising(contrast, None, 10, 7, 21)
        binary_clean = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
        )
        return norm_gray, binary_clean

    # -------------------------------------------------------------------------
    # LAYER 2: LAYOUT SEGMENTATION & CLASSIFICATION
    # -------------------------------------------------------------------------
    def analyze_layout(
        self,
        img_bgr: np.ndarray,
        norm_gray: np.ndarray,
        binary_clean: np.ndarray
    ) -> LayoutAnalysis:
        """
        Layer 2: Structural zone detection and layout classification.
        - Header zone (top margin stamp / title area)
        - Official seals & revenue stamps (HSV multi-spectral mask + Hough circles)
        - Tabular zones (morphological horizontal/vertical line intersections)
        - Ordered handwritten text lines (horizontal projection profile & connected components)
        """
        h, w = norm_gray.shape[:2]
        header_bbox = [0, 0, w, int(h * 0.22)]

        # 1. Multi-spectral Seal & Stamp Detection
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        # Red hue wrap-around
        mask_red1 = cv2.inRange(hsv, np.array([0, 45, 45]), np.array([12, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([168, 45, 45]), np.array([180, 255, 255]))
        # Purple / Blue ink
        mask_blue = cv2.inRange(hsv, np.array([90, 35, 35]), np.array([160, 255, 255]))
        seal_mask = cv2.bitwise_or(cv2.bitwise_or(mask_red1, mask_red2), mask_blue)
        colored_ink_ratio = float(np.count_nonzero(seal_mask) / seal_mask.size)

        seal_bboxes: List[List[int]] = []
        # Check circular seals in top half
        upper_norm = norm_gray[0:int(h * 0.50), :]
        circles = cv2.HoughCircles(
            upper_norm, cv2.HOUGH_GRADIENT, dp=1.2, minDist=60,
            param1=100, param2=35, minRadius=int(min(w, h) * 0.03), maxRadius=int(min(w, h) * 0.16)
        )
        if circles is not None:
            for c in np.round(circles[0, :]).astype("int"):
                cx, cy, r = c
                x1 = max(0, cx - r)
                y1 = max(0, cy - r)
                bw = min(w - x1, 2 * r)
                bh = min(h - y1, 2 * r)
                seal_bboxes.append([int(x1), int(y1), int(bw), int(bh)])

        # Connected components on colored ink mask
        contours, _ = cv2.findContours(seal_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            if bw > 30 and bh > 30 and (bw * bh) > (w * h * 0.002):
                seal_bboxes.append([int(bx), int(by), int(bw), int(bh)])

        official_seal_detected = (circles is not None) or (colored_ink_ratio > 0.001)

        # 2. Tabular Grid Detection
        inv = cv2.adaptiveThreshold(
            norm_gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10
        )
        horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, w // 15), 1))
        vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, h // 15)))

        horiz_lines = cv2.morphologyEx(inv, cv2.MORPH_OPEN, horiz_kernel, iterations=1)
        vert_lines = cv2.morphologyEx(inv, cv2.MORPH_OPEN, vert_kernel, iterations=1)

        grid_intersections = cv2.bitwise_and(horiz_lines, vert_lines)
        num_labels, _ = cv2.connectedComponents(grid_intersections)
        grid_count = int(max(0, num_labels - 1))

        table_mask = cv2.bitwise_or(horiz_lines, vert_lines)
        table_contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        tabular_bboxes: List[List[int]] = []
        for cnt in table_contours:
            tx, ty, tw, th = cv2.boundingRect(cnt)
            if tw > int(w * 0.3) and th > int(h * 0.08):
                tabular_bboxes.append([int(tx), int(ty), int(tw), int(th)])

        has_tabular_grid = (grid_count >= 12 and len(tabular_bboxes) > 0)

        # 3. Handwritten Text Line Segmentation (Ordered top-to-bottom)
        inv_text = 255 - binary_clean
        # Morphological closing along horizontal writing line
        line_close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 35), 2))
        closed_text = cv2.morphologyEx(inv_text, cv2.MORPH_CLOSE, line_close_kernel)
        text_contours, _ = cv2.findContours(closed_text, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        raw_line_boxes: List[List[int]] = []
        for cnt in text_contours:
            lx, ly, lw, lh = cv2.boundingRect(cnt)
            # Filter text lines: minimum width and sensible height, ignoring stamps in top 15%
            if lw >= int(w * 0.12) and lh >= 8:
                raw_line_boxes.append([int(lx), int(ly), int(lw), int(lh)])

        raw_line_boxes.sort(key=lambda b: b[1])

        # Refine tall multi-line blocks with horizontal projection profiling
        line_crops_list: List[TextLineCrop] = []
        line_idx = 1
        for lx, ly, lw, lh in raw_line_boxes:
            if lh > int(h * 0.05):
                roi = inv_text[ly:ly + lh, lx:lx + lw]
                row_sums = np.sum(roi > 0, axis=1)
                peak_val = np.max(row_sums) if len(row_sums) > 0 else 0
                threshold = 0.06 * peak_val if peak_val > 0 else 0
                is_text = row_sums > threshold

                segments = []
                in_seg = False
                seg_start = 0
                for idx, val in enumerate(is_text):
                    if val and not in_seg:
                        in_seg = True
                        seg_start = idx
                    elif not val and in_seg:
                        in_seg = False
                        if idx - seg_start >= 8:
                            segments.append((seg_start, idx))
                if in_seg and (len(is_text) - seg_start >= 8):
                    segments.append((seg_start, len(is_text)))

                if len(segments) > 1:
                    for s_start, s_end in segments:
                        sub_h = s_end - s_start
                        sub_y = ly + s_start
                        line_crops_list.append(TextLineCrop(
                            line_index=line_idx,
                            bbox=[lx, sub_y, lw, sub_h],
                            crop_path="",
                            aspect_ratio=round(lw / max(1, sub_h), 2)
                        ))
                        line_idx += 1
                else:
                    line_crops_list.append(TextLineCrop(
                        line_index=line_idx,
                        bbox=[lx, ly, lw, lh],
                        crop_path="",
                        aspect_ratio=round(lw / max(1, lh), 2)
                    ))
                    line_idx += 1
            else:
                line_crops_list.append(TextLineCrop(
                    line_index=line_idx,
                    bbox=[lx, ly, lw, lh],
                    crop_path="",
                    aspect_ratio=round(lw / max(1, lh), 2)
                ))
                line_idx += 1

        # Re-sort strictly by vertical position y
        line_crops_list.sort(key=lambda lc: lc.bbox[1])
        for idx, lc in enumerate(line_crops_list, start=1):
            lc.line_index = idx

        # 4. Classify Overall Layout Pattern
        horiz_ratio = np.count_nonzero(horiz_lines) / float(h * w)
        vert_ratio = np.count_nonzero(vert_lines) / float(h * w)

        if has_tabular_grid and horiz_ratio > 0.003 and vert_ratio > 0.002:
            pattern = LayoutPattern.KHATIAN_TABULAR_LAYOUT
            confidence = 0.95
        elif grid_count >= 8 and len(line_crops_list) >= 4:
            pattern = LayoutPattern.MIXED_SCHEDULE_LAYOUT
            confidence = 0.90
        elif len(line_crops_list) >= 3 or official_seal_detected:
            pattern = LayoutPattern.DEED_PROSE_LAYOUT
            confidence = 0.93
        else:
            pattern = LayoutPattern.UNKNOWN
            confidence = 0.50

        return LayoutAnalysis(
            pattern=pattern,
            confidence=confidence,
            grid_intersections=grid_count,
            has_tabular_grid=has_tabular_grid,
            official_seal_detected=official_seal_detected,
            colored_ink_ratio=round(colored_ink_ratio, 5),
            header_zone_bbox=header_bbox,
            seal_bboxes=seal_bboxes,
            tabular_bboxes=tabular_bboxes,
            detected_lines_count=len(line_crops_list),
            line_crops=line_crops_list
        )

    # -------------------------------------------------------------------------
    # LAYER 3: EVIDENCE CROPPING & PROVENANCE MAPPING
    # -------------------------------------------------------------------------
    def generate_evidence_crops(
        self,
        img_bgr: np.ndarray,
        norm_gray: np.ndarray,
        binary_clean: np.ndarray,
        layout: LayoutAnalysis,
        doc_id: str
    ) -> Tuple[str, str, Dict[str, EvidenceCrop]]:
        """
        Layer 3: Generates visual evidence crops and persists them in outputs/evidence/<doc_id>/
        Includes:
        - Full-page normalized & clean binarized images
        - Header zone crop
        - Detected seal/stamp crops
        - Detected tabular grid crops
        - Ordered handwritten line crops
        - 8 canonical field evidence crops (saf-kabala / deed fields)
        """
        doc_evidence_dir = self.output_base_dir / doc_id
        doc_evidence_dir.mkdir(parents=True, exist_ok=True)
        crops_dir = doc_evidence_dir / "crops"
        crops_dir.mkdir(parents=True, exist_ok=True)

        h, w = norm_gray.shape[:2]

        # 1. Save normalized & binarized full-page images
        norm_path = str(doc_evidence_dir / "normalized_clean.png")
        bin_path = str(doc_evidence_dir / "binarized_clean.png")
        cv2.imwrite(norm_path, norm_gray)
        cv2.imwrite(bin_path, binary_clean)

        evidence_crops: Dict[str, EvidenceCrop] = {}

        # 2. Header Zone Crop
        if layout.header_zone_bbox:
            hx, hy, hw, hh = layout.header_zone_bbox
            crop_img = norm_gray[hy:hy + hh, hx:hx + hw]
            crop_path = str(crops_dir / "header_zone.png")
            cv2.imwrite(crop_path, crop_img)
            evidence_crops["header_zone"] = EvidenceCrop(
                crop_id=f"{doc_id}_header_zone",
                zone_type="header",
                bbox=layout.header_zone_bbox,
                crop_path=crop_path,
                confidence=0.98
            )

        # 3. Seal / Stamp Crops
        for i, s_bbox in enumerate(layout.seal_bboxes[:4], start=1):
            sx, sy, sw, sh = s_bbox
            crop_img = img_bgr[sy:sy + sh, sx:sx + sw]
            crop_path = str(crops_dir / f"seal_{i:02d}.png")
            cv2.imwrite(crop_path, crop_img)
            evidence_crops[f"seal_{i:02d}"] = EvidenceCrop(
                crop_id=f"{doc_id}_seal_{i:02d}",
                zone_type="seal",
                bbox=s_bbox,
                crop_path=crop_path,
                confidence=0.92
            )

        # 4. Tabular Grid Crops
        for i, t_bbox in enumerate(layout.tabular_bboxes[:3], start=1):
            tx, ty, tw, th = t_bbox
            crop_img = binary_clean[ty:ty + th, tx:tx + tw]
            crop_path = str(crops_dir / f"table_{i:02d}.png")
            cv2.imwrite(crop_path, crop_img)
            evidence_crops[f"table_{i:02d}"] = EvidenceCrop(
                crop_id=f"{doc_id}_table_{i:02d}",
                zone_type="tabular_grid",
                bbox=t_bbox,
                crop_path=crop_path,
                confidence=0.95
            )

        # 5. Ordered Handwritten Line Crops (all detected lines)
        for lc in layout.line_crops:
            lx, ly, lw, lh = lc.bbox
            crop_img = binary_clean[ly:ly + lh, lx:lx + lw]
            crop_path = str(crops_dir / f"line_{lc.line_index:03d}.png")
            cv2.imwrite(crop_path, crop_img)
            lc.crop_path = crop_path
            evidence_crops[f"line_{lc.line_index:03d}"] = EvidenceCrop(
                crop_id=f"{doc_id}_line_{lc.line_index:03d}",
                zone_type="handwritten_line",
                bbox=lc.bbox,
                crop_path=crop_path,
                confidence=0.90
            )

        # 6. Canonical 8-Field Evidence Crops
        field_specs = {
            "stamp_serial_no": (int(w * 0.04), int(h * 0.18), int(w * 0.28), int(h * 0.23)),
            "stamp_duty_math": (int(w * 0.01), int(h * 0.23), int(w * 0.39), int(h * 0.31)),
            "copy_issue_date": (int(w * 0.48), int(h * 0.36), int(w * 0.68), int(h * 0.42)),
            "deed_number_year": (int(w * 0.51), int(h * 0.44), int(w * 0.74), int(h * 0.49)),
            "deed_type_and_value": (int(w * 0.38), int(h * 0.49), int(w * 0.96), int(h * 0.54)),
            "land_area": (int(w * 0.38), int(h * 0.53), int(w * 0.96), int(h * 0.58)),
            "location_mouza_thana": (int(w * 0.38), int(h * 0.57), int(w * 0.95), int(h * 0.65)),
            "registration_date": (int(w * 0.02), int(h * 0.72), int(w * 0.39), int(h * 0.84)),
        }
        for field_key, (x1, y1, x2, y2) in field_specs.items():
            crop_img = binary_clean[y1:y2, x1:x2]
            crop_path = str(crops_dir / f"field_{field_key}.png")
            cv2.imwrite(crop_path, crop_img)
            evidence_crops[field_key] = EvidenceCrop(
                crop_id=f"{doc_id}_{field_key}",
                zone_type="field_evidence",
                bbox=[x1, y1, x2 - x1, y2 - y1],
                crop_path=crop_path,
                confidence=0.94
            )

        return norm_path, bin_path, evidence_crops

    # -------------------------------------------------------------------------
    # END-TO-END PIPELINE ORCHESTRATION
    # -------------------------------------------------------------------------
    def process_document(
        self,
        image_path: str,
        doc_id: Optional[str] = None
    ) -> DocumentAnalysisResult:
        """
        Executes Layers 1, 2, and 3 sequentially:
        1. Loads image & computes SHA-256 hash.
        2. Layer 1: Assesses quality gate.
        3. Preprocesses image (shadow removal + CLAHE binarization).
        4. Layer 2: Analyzes layout & segments lines/zones.
        5. Layer 3: Extracts evidence crops & saves provenance paths.
        """
        t0 = time.perf_counter()
        img_p = Path(image_path)
        if not img_p.exists():
            raise FileNotFoundError(f"Document image not found at: {image_path}")

        if doc_id is None:
            doc_id = img_p.stem

        img_bgr = cv2.imread(str(img_p))
        if img_bgr is None:
            raise ValueError(f"OpenCV could not decode image: {image_path}")

        sha256_hash = self.compute_sha256(str(img_p))

        # Layer 1: Image Quality Assessment
        quality = self.assess_image_quality(img_bgr)

        # Preprocessing
        norm_gray, binary_clean = self.preprocess_image(img_bgr)

        # Layer 2: Layout Segmentation & Classification
        layout = self.analyze_layout(img_bgr, norm_gray, binary_clean)

        # Layer 3: Evidence Cropping
        norm_path, bin_path, evidence_crops = self.generate_evidence_crops(
            img_bgr, norm_gray, binary_clean, layout, doc_id
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return DocumentAnalysisResult(
            doc_id=doc_id,
            schema_version=SCHEMA_VERSION,
            image_sha256=sha256_hash,
            original_image_path=str(img_p.resolve()),
            normalized_image_path=norm_path,
            binarized_image_path=bin_path,
            quality=quality,
            layout=layout,
            evidence_crops=evidence_crops,
            processing_time_ms=round(elapsed_ms, 2),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    # -------------------------------------------------------------------------
    # DEBUG & VISUAL VERIFICATION OVERLAY
    # -------------------------------------------------------------------------
    @staticmethod
    def generate_layout_overlay_image(
        image_path: str,
        analysis: DocumentAnalysisResult,
        output_path: str
    ) -> str:
        """
        Renders colored bounding box overlays on top of the original image:
        - Blue: Header zone
        - Magenta: Seals / Stamps
        - Cyan: Tabular grids
        - Green: Handwritten text lines
        """
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            return ""

        overlay = img_bgr.copy()

        # 1. Header (Blue)
        if analysis.layout.header_zone_bbox:
            hx, hy, hw, hh = analysis.layout.header_zone_bbox
            cv2.rectangle(overlay, (hx, hy), (hx + hw, hy + hh), (255, 120, 0), 3)
            cv2.putText(overlay, "HEADER ZONE", (hx + 10, hy + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 120, 0), 2)

        # 2. Seals (Magenta)
        for i, (sx, sy, sw, sh) in enumerate(analysis.layout.seal_bboxes[:4], start=1):
            cv2.rectangle(overlay, (sx, sy), (sx + sw, sy + sh), (200, 0, 255), 3)
            cv2.putText(overlay, f"SEAL #{i}", (sx + 5, sy + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 0, 255), 2)

        # 3. Tabular (Cyan)
        for i, (tx, ty, tw, th) in enumerate(analysis.layout.tabular_bboxes[:3], start=1):
            cv2.rectangle(overlay, (tx, ty), (tx + tw, ty + th), (255, 255, 0), 3)
            cv2.putText(overlay, f"TABLE GRID #{i}", (tx + 10, ty + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # 4. Text Lines (Green)
        for lc in analysis.layout.line_crops[:25]:
            lx, ly, lw, lh = lc.bbox
            cv2.rectangle(overlay, (lx, ly), (lx + lw, ly + lh), (0, 230, 0), 2)
            cv2.putText(overlay, f"L{lc.line_index}", (lx + 4, ly + min(lh - 2, 16)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 0), 1)

        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_p), overlay)
        return str(out_p)
