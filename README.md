# SegmentFlow

AI-Assisted Video Segmentation

A web-based AI-assisted video instance segmentation labeling tool using SAM3 (Segment Anything Model 3) for semi-automated annotation. The system enables users to manually label key frames and automatically propagate labels across video sequences, drastically reducing labeling time.

Tech Stack: FastAPI (Backend) + Vue 3 (Frontend) + SAM3 + SQLite/PostgreSQL

Target Users: ML engineers, data annotators, computer vision researchers

Key Differentiator: GPU-accelerated video propagation with real-time SAM3 inference (<50ms latency)
