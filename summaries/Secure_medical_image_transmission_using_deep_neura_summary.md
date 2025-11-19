# Professional Summary: Secure Medical Image Transmission Using Deep Neural Network in E-Health Applications

## 📋 Article Metadata
**Title:** Secure medical image transmission using deep neural network in e-health applications  
**Authors:** Ala Abdulsalam Alarood, Muhammad Faheem, Abdullah I. A. Alzahrani, Abdulrahman A. Alshdadi  
**Institutions:**  
- University of Jeddah, Saudi Arabia  
- University of Vaasa, Finland  
- Skyline University College, UAE  
- Shaqra University, Saudi Arabia  
**Journal:** Healthcare Technology Letters  
**Volume:** 10, pp. 87-98 (2023)  
**DOI:** https://doi.org/10.1049/htl2.12049  
**Funding:** University of Vaasa and the Academy of Finland

---

## 🎯 Research Overview

This research presents an innovative **hybrid encryption system** that combines **Deep Neural Networks (DNN)** with **chaotic systems** for securing medical image transmission in e-health applications. The method addresses the critical security requirements of medical imaging by leveraging DNN's adaptive capabilities for intelligent image segmentation and chaotic systems for generating highly random encryption keys.

---

## 🔑 Key Research Components

### 1. **Problem Statement & Motivation**

**Healthcare Security Challenges:**
- Rapid growth of Internet-based e-health systems
- Medical images transmitted across network branches vulnerable to attacks
- Unauthorized access to sensitive patient data
- Need for high-level security without compromising diagnostic quality

**Medical Image Characteristics:**
- High redundancy
- Strong correlation between adjacent pixels
- Huge data size
- Require special encryption effort (speed + accuracy)

**Traditional Encryption Limitations:**
- Not suitable for large medical images
- Vulnerable to attacks during online transmission
- Inefficient for real-time applications
- Linear transformations easily breakable

---

### 2. **Proposed Hybrid Method Architecture**

#### **Core Innovation: DNN + Chaotic System Integration**

**A. Chaotic Key Generation (Henon Map)**

The system uses the Henon Map for generating pseudo-random encryption keys:

**Equation:**
```
X_{n+1} = 1 - aX_n² + Y_n
Y_{n+1} = bX_n
```

**Parameters:**
- a = 1.4, b = 0.3 (chaotic behavior parameters)
- x₀, y₀: Initial conditions
- High sensitivity to initial conditions
- Non-periodic behavior

**Key Generation Process:**
1. Initial key of 128 bits generated
2. Bit stream of random sequence formed
3. Variable iterations for enhanced security

**Key Space:** 10³⁵ (resistant to brute-force attacks)

**B. Deep Neural Network Integration**

**DNN Roles:**
1. **Intelligent Image Segmentation:**
   - Divides image into Region of Interest (ROI) blocks
   - Block size: 32×32 pixels (n=4)
   - Adaptive partitioning based on image features

2. **Weight-Based Optimization:**
   - Identifies weights with highest impact on output
   - Controls intermediate and semi-final outputs
   - Adaptive layer structure based on prediction accuracy

3. **Pixel Distribution Control:**
   - Random pixel scrambling within designated areas
   - Dynamic confusion and diffusion processes

**Neural Network Structure:**
- Input Layer: Receives medical image data
- Hidden Layers: Variable depth based on complexity
- Output Layer: Encrypted image generation

**Key Equations:**

**Weight Calculation:**
```
Y_{nm} = w_{nm} · X_m
```

**Output Signal:**
```
y_k(n) = Σ w^(i+1) x_j(n-1)  [i=0 to ∞]
```

**Weight Classification:**
- |w| < 1: Stable system (exponential decay)
- |w| = 1: Linear behavior
- |w| > 1: Negative exponential

---

### 3. **Encryption Process (Two-Stage)**

#### **Stage 1: Confusion (Position Scrambling)**

**Objectives:**
- Change pixel positions
- Destroy structural dependencies
- Randomize image appearance

**Methods:**
1. **Column Scrambling:** Rearrange columns using chaotic sequence
2. **Row Scrambling:** Rearrange rows independently
3. **Sub-block Randomization:** DNN-guided block redistribution

**DNN Contribution:**
- Selects image partitions adaptively
- Determines scrambling patterns
- Updates cipher key dynamically

#### **Stage 2: Diffusion (Value Modification)**

**Objectives:**
- Change pixel values
- Generate noise
- Eliminate pixel correlation

**Process:**
1. Convert pixels to vector format
2. Apply DNN-controlled value changes (vertical & horizontal)
3. Perform OR operation: Pixel ⊕ Key ⊕ Scrambled_Vector
4. Update cipher key continuously

**Result:** Encrypted image with no discernible patterns

---

### 4. **Algorithm Workflow**

**ALGORITHM 1: General Proposed Stage for Image Encryption Using DNN**

```
1. Read images from dataset
2. For all images do:
   2.1 Preprocessing given image
   2.2 Extract features from image
   2.3 Create Neural Network
   2.4 Determine effective parameters in network
3. Update hidden layers and nodes according to parameters
4. Confusion process:
   4.1 Use DNN to select image partition
   4.2 For each partition use DNN for scrambling
   4.3 Update cipher key
5. Diffusion process:
   5.1 While not End-Of-Image:
       5.1.1 Move pixels into vector
       5.1.2 Use DNN to change pixel value (vertically & horizontally)
       5.1.3 Update cipher key
6. Save/transmit encrypted image
7. Return to step 2
```

---

## 📊 Experimental Setup & Dataset

**Implementation Environment:**
- **Platform:** MATLAB 2015a
- **Hardware:** Core i9 CPU @ 3.9 GHz, 32 GB RAM
- **OS:** Fedora 32
- **Image Resolution:** 512×512 pixels
- **Block Size:** 32×32
- **Iterations:** 10,000

**Dataset:**
- **Primary Source:** Standard brain tomography dataset
- **Image Types:** Color and grayscale medical images
- **Classes:** 5 different medical image categories
- **Adaptability:** Works with various image dimensions

---

## 🔬 Performance Evaluation Results

### **1. Information Entropy Analysis**

**Metric:** Measures randomness of encrypted image

**Equation:**
```
H(m) = Σ P(m) log₂(1/P(m))
```

**Results:**

| Tested Image | Entropy | Ideal (8-bit) |
|--------------|---------|---------------|
| Image 1 | 7.9992 | 8.0 |
| Image 2 | 7.9994 | 8.0 |
| Image 3 | 7.9993 | 8.0 |
| Image 4 | 7.9984 | 8.0 |
| Image 5 | 7.9989 | 8.0 |

**Interpretation:** Near-perfect randomness achieved (≈8.0)

---

### **2. Histogram Analysis**

**Purpose:** Verify uniform pixel distribution in encrypted image

**Chi-Square Test Results:**

| Given Image | Chi-Square Value |
|-------------|------------------|
| Image 1 | 260.9 |
| Image 2 | 241.1 |
| Image 3 | 231.5 |
| Image 4 | 270.5 |
| Image 5 | 212.8 |

**Observation:** Encrypted images show uniform distribution, preventing attackers from guessing image information

**Chi-Square Equation:**
```
X² = Σ [(Oᵢ - EV)² / EV]  [i=1 to 256]
```
where Oᵢ = occurrence rate for grey value i, EV = O/256

---

### **3. Correlation Coefficient Analysis**

**Purpose:** Measure pixel correlation destruction

**Equations:**
```
r(A,B) = E((A-E(A))(B-E(B))) / √(D(A)D(B))
E(A) = (1/S) Σ Aᵢ
D(A) = (1/S) Σ (Aᵢ - E(A))²
```

**Results (Proposed Method):**

| Image | Direction | Original | Encrypted |
|-------|-----------|----------|----------|
| Image 1 | Vertical | 0.987 | -0.011 |
|  | Horizontal | 0.976 | 0.019 |
|  | Diagonal | 0.962 | 0.014 |
| Image 2 | Vertical | 0.991 | 0.005 |
|  | Horizontal | 0.991 | -0.007 |
|  | Diagonal | 0.976 | -0.041 |
| Image 5 | Vertical | 0.981 | 0.062 |
|  | Horizontal | 0.973 | 0.081 |
|  | Diagonal | 0.942 | 0.062 |

**Benchmark Comparison:**

| Method | Horizontal | Vertical | Diagonal |
|--------|-----------|----------|----------|
| **Proposed** | **-0.007** | **0.005** | **-0.041** |
| [46] | -0.001 | 0.009 | -0.003 |
| [47] | 0.002 | 0.001 | 0.001 |
| [48] | 0.002 | -0.001 | 0.000 |
| [49] | 0.094 | 0.005 | 0.006 |

**Interpretation:** Correlation ≈ 0 indicates complete structural destruction

---

### **4. Differential Attack Resistance**

**Metrics:**
- **NPCR (Number of Pixels Change Rate):** Sensitivity to single-pixel changes
- **UACI (Unified Average Changing Intensity):** Average intensity change magnitude

**Equations:**
```
NPCR = (1/MN) Σ D(i,j) × 100%
UACI = (1/MN) Σ |E₁(i,j) - E₂(i,j)|/255 × 100%
```

**Results:**

| Image | NPCR (%) | UACI (%) |
|-------|----------|----------|
| Image 1 | 99.60 | 33.41 |
| Image 2 | 99.61 | 33.40 |
| Image 3 | 99.63 | 33.44 |
| Image 4 | 99.61 | 33.45 |

**Benchmark Comparison:**

| Method | NPCR (%) | UACI (%) |
|--------|----------|----------|
| **Proposed** | **99.61** | **33.42** |
| [46] | 99.61 | 33.26 |
| [47] | 99.53 | 33.45 |
| [48] | 99.51 | 33.39 |
| [17] | 99.60 | 33.49 |

**Interpretation:** 
- NPCR ≈ 99.6% → Single pixel change affects ~99.6% of encrypted image
- UACI ≈ 33.4% → Significant intensity variation
- Both values indicate **strong resistance to differential attacks**

---

### **5. Key Space Analysis**

**Requirement:** Key space ≥ 2¹⁰⁰ for security

**Calculation:**
- Y₀ accuracy: 10¹⁶
- Iteration number N₀: 10³
- **Total Key Space: 10³⁵**

**Conclusion:** Far exceeds minimum requirement, **resistant to brute-force attacks**

---

## 💡 Key Innovations & Contributions

### **1. Hybrid DNN-Chaotic System**
- **First Integration:** DNN adaptive capabilities + Chaotic randomness
- **Synergy:** DNN provides intelligent segmentation, chaos provides unpredictability
- **Non-detectable:** Chaotic system behavior not traceable by DNN analysis

### **2. Weight-Based Adaptive Encryption**
- Identifies neural network weights with highest output impact
- Dynamically adjusts hidden layers based on effectiveness
- Feedback loop optimizes encryption strength

### **3. Region of Interest (ROI) Approach**
- DNN-guided intelligent image partitioning
- Focuses encryption effort on critical areas
- Maintains diagnostic quality while ensuring security

### **4. Dual-Stage Confusion-Diffusion**
- **Confusion:** DNN-controlled position scrambling
- **Diffusion:** DNN-modulated value modification
- **Dynamic Key Update:** Continuous cipher key evolution

---

## 🏥 Medical Image Applications (Deep Learning Context)

The paper provides comprehensive background on DNN applications in medical imaging:

### **1. Diabetic Retinopathy Detection**
- **Algorithm:** Deep Convolutional Neural Network (DCNN)
- **Dataset:** EyePACS-1 (847 patients)
- **Accuracy:** >95%

### **2. Histological & Microscopic Analysis**
- Cancer cell detection in colon
- Breast cancer early diagnosis
- Thoracic lymph node analysis

### **3. Gastrointestinal Disease Detection**
- Hemorrhage detection in capsule endoscopy
- FCN + LSTM for feature extraction
- CNN for inflammatory disease classification

### **4. Cardiac Imaging**
- Calcium score measurement
- MRI-based heart diagnosis
- SVM classification of heart features

### **5. Tumor Detection**
- Benign vs. malignant classification
- Mammogram analysis (482 images)
- CNN for clustering-based diagnosis

### **6. Alzheimer's & Parkinson's Detection**
- Deep Boltzmann Machine (DBM) for feature extraction
- 3D MRI analysis with CNN
- 98% accuracy for Alzheimer's detection

---

## ⚖️ Advantages vs. Limitations

### **Advantages:**

✅ **High Security:**
- Near-perfect entropy (≈8.0)
- Near-zero correlation (≈0)
- Strong differential attack resistance (NPCR ≈99.6%)
- Large key space (10³⁵)

✅ **Adaptive Intelligence:**
- DNN-based dynamic encryption
- Context-aware image partitioning
- Self-optimizing hidden layers

✅ **Real-Time Feasibility:**
- Efficient computational performance
- Suitable for online transmission
- Hardware acceleration compatible

✅ **Universal Compatibility:**
- Works with color and grayscale images
- Adaptable to various image dimensions
- Multiple medical imaging modalities

### **Limitations (Acknowledged):**

⚠️ **Computational Load:**
- DNN training requires significant time
- Complex implementation effort
- Higher resource requirements than traditional methods

⚠️ **Key Management:**
- Key loss = impossible decryption
- Need for secure key storage
- Future: Key recovery mechanisms required

⚠️ **Compression Incompatibility:**
- Data loss possible during compression/resizing
- Complexity in handling scaled images
- Future: Adaptive compression support needed

---

## 🔬 Technical Deep Dive: Neural Network Design

### **Weight Behavior Classification:**

**System Stability Analysis:**

1. **Stable System (|w| < 1):**
   - Exponential decay of signal
   - Finite sum achievable
   - Preferred for encryption

2. **Linear System (|w| = 1):**
   - Constant signal behavior
   - Predictable pattern
   - Avoided in encryption

3. **Unstable System (|w| > 1):**
   - Negative exponential growth
   - Unpredictable behavior
   - Controlled usage in diffusion

### **Data Flow Control:**

**XOR Operations:**
- Implemented during iterations
- Multiple flow directions (forward/feedback)
- Creates non-linear transformations

**Node Creation Logic:**
```
IF (w_n + w_{n+1}) > 0 THEN x+2 = 1
IF (x_i, x_r(n+2)) = 1 THEN create new node
```

### **Recurrent Network Integration:**
- Feedback loops enhance accuracy
- At least one backward connection
- Distinguishes from feed-forward networks

---

## 📈 Comparative Analysis

### **vs. Traditional Chaotic Encryption:**
- ✅ Adaptive image partitioning (DNN)
- ✅ Intelligent scrambling patterns
- ✅ Dynamic key updates
- ❌ Higher computational cost

### **vs. Pure DNN Approaches:**
- ✅ Enhanced randomness (chaotic system)
- ✅ Larger key space
- ✅ Better entropy scores
- ⚖️ Similar computational requirements

### **vs. Benchmark Methods ([46]-[49]):**
- ✅ Competitive or superior correlation coefficients
- ✅ Comparable NPCR/UACI values
- ✅ Higher entropy (closer to ideal 8.0)
- ✅ Novel DNN integration approach

---

## 🚀 Future Research Directions

### **Recommended Enhancements:**

1. **Key Recovery Mechanisms:**
   - Multi-factor authentication integration
   - Distributed key storage
   - Quantum-resistant key generation

2. **Compression Support:**
   - Lossless compression compatibility
   - Adaptive scaling mechanisms
   - Format-agnostic encryption

3. **Performance Optimization:**
   - GPU acceleration for DNN training
   - Parallel processing implementation
   - Real-time video encryption extension

4. **Enhanced DNN Architectures:**
   - Deeper network structures
   - Attention mechanisms integration
   - Transfer learning for faster adaptation

5. **IoMT Integration:**
   - Lightweight versions for edge devices
   - Blockchain for secure key distribution
   - 5G-optimized transmission protocols

---

## 🎓 Academic & Practical Significance

### **Theoretical Contributions:**
- Novel hybrid encryption framework (DNN + Chaos)
- Mathematical proof of security through multi-metric validation
- Adaptive neural network design for cryptography

### **Practical Applications:**

1. **E-Health Platforms:**
   - Secure telemedicine consultations
   - Remote diagnosis systems
   - Cloud-based medical record storage

2. **Hospital Networks:**
   - Intra-hospital secure communication
   - PACS (Picture Archiving and Communication Systems)
   - Medical image sharing between facilities

3. **Research Collaboration:**
   - Anonymized medical image databases
   - Multi-institutional studies
   - AI training dataset protection

4. **Regulatory Compliance:**
   - HIPAA-compliant transmission
   - GDPR data protection
   - ISO 27001 information security

---

## 📊 Performance Summary

| Aspect | Achievement | Interpretation |
|--------|-------------|----------------|
| **Entropy** | 7.9992 | Near-perfect randomness |
| **Correlation** | ~0.005 | Complete structure destruction |
| **NPCR** | 99.61% | High sensitivity to changes |
| **UACI** | 33.42% | Strong intensity variation |
| **Key Space** | 10³⁵ | Brute-force resistant |
| **Chi-Square** | 212-270 | Uniform distribution |

---

## 🏆 Conclusion

The research successfully demonstrates that **integrating Deep Neural Networks with chaotic systems** creates a powerful medical image encryption framework that:

✅ **Achieves exceptional security** through adaptive intelligence and chaotic randomness  
✅ **Maintains computational efficiency** suitable for real-time e-health applications  
✅ **Resists multiple attack vectors** (differential, statistical, brute-force)  
✅ **Preserves diagnostic quality** through intelligent ROI-based encryption  
✅ **Scales effectively** across different medical imaging modalities  

This hybrid approach represents a significant advancement in medical image security, addressing the critical need for robust encryption in modern digital healthcare environments while maintaining the balance between security, efficiency, and usability.

---

**Document Type:** Research Article (Peer-Reviewed Journal)  
**Research Methodology:** Experimental Design with Quantitative Security Analysis  
**Primary Innovation:** DNN-Chaotic Hybrid Cryptosystem for Medical Imaging  
**Target Audience:** Healthcare IT professionals, medical informatics specialists, cryptography researchers  

**Keywords:** Medical Image Encryption, Deep Neural Network, Chaotic Systems, E-Health Security, Henon Map, Confusion-Diffusion, HIPAA Compliance, Telemedicine Security, Region of Interest, Adaptive Cryptography