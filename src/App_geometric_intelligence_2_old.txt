import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Brain, Play, Pause, RotateCcw, Download, Video, Layers, Zap, Eye, Lightbulb, Save, Upload } from 'lucide-react';

const FIELD_SIZE = 256;
const MAX_SCOUTS = 4000;
const ATTRACTOR_TYPES = 12;
const MEMORY_DECAY = 0.995; // Slow memory decay for persistence
const DREAM_THRESHOLD = 0.1; // When to start dreaming (low visual input)

// Scout Types - Each is a "minimodel" like V1 neurons
const SCOUT_TYPES = {
    EDGE_VERTICAL: 0,
    EDGE_HORIZONTAL: 1,
    EDGE_DIAGONAL_1: 2,
    EDGE_DIAGONAL_2: 3,
    MOTION_UP: 4,
    MOTION_DOWN: 5,
    MOTION_LEFT: 6,
    MOTION_RIGHT: 7,
    COLOR_BRIGHT: 8,
    COLOR_DARK: 9,
    TEXTURE_HIGH: 10,
    TEXTURE_LOW: 11
};

const SCOUT_COLORS = {
    [SCOUT_TYPES.EDGE_VERTICAL]: '#ff0000',
    [SCOUT_TYPES.EDGE_HORIZONTAL]: '#ff4400',
    [SCOUT_TYPES.EDGE_DIAGONAL_1]: '#ff8800',
    [SCOUT_TYPES.EDGE_DIAGONAL_2]: '#ffcc00',
    [SCOUT_TYPES.MOTION_UP]: '#00ff00',
    [SCOUT_TYPES.MOTION_DOWN]: '#00ff88',
    [SCOUT_TYPES.MOTION_LEFT]: '#00ffff',
    [SCOUT_TYPES.MOTION_RIGHT]: '#0088ff',
    [SCOUT_TYPES.COLOR_BRIGHT]: '#ffffff',
    [SCOUT_TYPES.COLOR_DARK]: '#888888',
    [SCOUT_TYPES.TEXTURE_HIGH]: '#ff00ff',
    [SCOUT_TYPES.TEXTURE_LOW]: '#8800ff'
};

// Enhanced Psi Field with Memory and Dreaming
class DreamingPsiField {
    constructor() {
        this.width = FIELD_SIZE;
        this.height = FIELD_SIZE;
        this.current = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.previous = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.history = [];
        this.maxHistory = 10;
        
        // Feature maps - the "core layer"
        this.edgeMap = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.motionMap = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.colorMap = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.textureMap = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        
        // Attractor field with memory
        this.attractorField = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.attractorMemory = new Float32Array(FIELD_SIZE * FIELD_SIZE); // Persistent memory
        this.memoryStrength = new Float32Array(FIELD_SIZE * FIELD_SIZE); // How strong each memory is
        
        // Dreaming state
        this.isDreaming = false;
        this.dreamIntensity = 0;
        this.visualInputStrength = 1.0;
        
        // VAE-like memory associations
        this.memoryPatterns = new Map(); // Store attractor pattern -> visual pattern associations
        this.patternHistory = [];
    }
    
    updateFromImage(imageData) {
        // Calculate visual input strength (how much actual visual information is present)
        let totalIntensity = 0;
        for (let i = 0; i < imageData.data.length; i += 4) {
            totalIntensity += (imageData.data[i] + imageData.data[i + 1] + imageData.data[i + 2]) / 3;
        }
        this.visualInputStrength = totalIntensity / (imageData.data.length / 4 * 255);
        
        // Determine if we should be dreaming (low visual input = covered camera)
        this.isDreaming = this.visualInputStrength < DREAM_THRESHOLD;
        
        if (this.isDreaming) {
            this.enterDreamState();
        } else {
            this.processRealVisualInput(imageData);
        }
        
        this.computeFeatureMaps();
        this.updateMemory();
    }
    
    processRealVisualInput(imageData) {
        // Store previous state
        this.previous.set(this.current);
        
        // Convert to luminance and update current
        for (let i = 0; i < this.current.length; i++) {
            const r = imageData.data[i * 4] / 255;
            const g = imageData.data[i * 4 + 1] / 255;
            const b = imageData.data[i * 4 + 2] / 255;
            this.current[i] = 0.299 * r + 0.587 * g + 0.114 * b;
        }
        
        // Add to history
        this.history.push(new Float32Array(this.current));
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        }
        
        // Reset dream intensity when we have real input
        this.dreamIntensity *= 0.9;
    }
    
    enterDreamState() {
        // When camera is covered, start dreaming based on memory
        this.dreamIntensity = Math.min(1.0, this.dreamIntensity + 0.02);
        
        // Generate dream content from attractor memory
        this.generateDreamContent();
        
        // Update current field based on dream content
        for (let i = 0; i < this.current.length; i++) {
            // Blend memory with autonomous drift
            const memoryContent = this.attractorMemory[i];
            const drift = (Math.random() - 0.5) * 0.1 * this.dreamIntensity;
            this.current[i] = memoryContent + drift;
        }
        
        // Add dream frame to history
        this.history.push(new Float32Array(this.current));
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        }
    }
    
    generateDreamContent() {
        // This is where the magic happens - autonomous attractor evolution
        for (let i = 0; i < this.attractorMemory.length; i++) {
            const x = i % this.width;
            const y = Math.floor(i / this.width);
            
            // Add slow, wave-like evolution to memory patterns
            const time = Date.now() * 0.001;
            const wave1 = Math.sin(x * 0.1 + time) * 0.1;
            const wave2 = Math.cos(y * 0.1 + time * 0.7) * 0.1;
            const wave3 = Math.sin((x + y) * 0.05 + time * 0.3) * 0.05;
            
            // Evolve attractors based on their memory strength
            if (this.memoryStrength[i] > 0.1) {
                this.attractorMemory[i] += (wave1 + wave2 + wave3) * this.dreamIntensity * this.memoryStrength[i];
                this.attractorMemory[i] = Math.max(0, Math.min(1, this.attractorMemory[i]));
            }
        }
    }
    
    computeFeatureMaps() {
        // Edge detection (enhanced for dream state)
        for (let y = 1; y < this.height - 1; y++) {
            for (let x = 1; x < this.width - 1; x++) {
                const idx = y * this.width + x;
                
                // Sobel edge detection
                const gx = (
                    -this.current[idx - this.width - 1] + this.current[idx - this.width + 1] +
                    -2 * this.current[idx - 1] + 2 * this.current[idx + 1] +
                    -this.current[idx + this.width - 1] + this.current[idx + this.width + 1]
                );
                
                const gy = (
                    -this.current[idx - this.width - 1] - 2 * this.current[idx - this.width] - this.current[idx - this.width + 1] +
                    this.current[idx + this.width - 1] + 2 * this.current[idx + this.width] + this.current[idx + this.width + 1]
                );
                
                this.edgeMap[idx] = Math.sqrt(gx * gx + gy * gy);
                
                // Motion detection (works even in dream state)
                if (this.history.length >= 2) {
                    const motion = Math.abs(this.current[idx] - this.previous[idx]);
                    this.motionMap[idx] = motion;
                }
                
                // Color intensity
                this.colorMap[idx] = this.current[idx];
                
                // Texture (local variance)
                let variance = 0;
                let count = 0;
                const mean = this.current[idx];
                for (let dy = -1; dy <= 1; dy++) {
                    for (let dx = -1; dx <= 1; dx++) {
                        const nidx = (y + dy) * this.width + (x + dx);
                        if (nidx >= 0 && nidx < this.current.length) {
                            variance += (this.current[nidx] - mean) * (this.current[nidx] - mean);
                            count++;
                        }
                    }
                }
                this.textureMap[idx] = variance / count;
            }
        }
    }
    
    updateAttractorField(scouts) {
        // Reset attractor field
        this.attractorField.fill(0);
        
        // Each scout contributes to the field
        scouts.forEach(scout => {
            const x = Math.floor(scout.x);
            const y = Math.floor(scout.y);
            if (x >= 0 && x < this.width && y >= 0 && y < this.height) {
                const idx = y * this.width + x;
                this.attractorField[idx] += scout.activation * 0.1;
            }
        });
        
        // Smooth the attractor field
        this.smoothField(this.attractorField);
    }
    
    updateMemory() {
        // Update persistent memory based on attractor field
        for (let i = 0; i < this.attractorField.length; i++) {
            const currentStrength = this.attractorField[i];
            
            if (currentStrength > 0.1) {
                // Strengthen memory where attractors are active
                this.memoryStrength[i] = Math.min(1.0, this.memoryStrength[i] + 0.01);
                this.attractorMemory[i] = this.attractorMemory[i] * 0.95 + currentStrength * 0.05;
            } else {
                // Gradual memory decay
                this.memoryStrength[i] *= MEMORY_DECAY;
                if (this.memoryStrength[i] < 0.01) {
                    this.attractorMemory[i] *= 0.99; // Very slow forgetting
                }
            }
        }
    }
    
    smoothField(field) {
        const temp = new Float32Array(field.length);
        for (let y = 1; y < this.height - 1; y++) {
            for (let x = 1; x < this.width - 1; x++) {
                const idx = y * this.width + x;
                let sum = 0;
                let count = 0;
                for (let dy = -1; dy <= 1; dy++) {
                    for (let dx = -1; dx <= 1; dx++) {
                        const nidx = (y + dy) * this.width + (x + dx);
                        sum += field[nidx];
                        count++;
                    }
                }
                temp[idx] = sum / count;
            }
        }
        field.set(temp);
    }
    
    exportMemoryState() {
        return {
            attractorMemory: Array.from(this.attractorMemory),
            memoryStrength: Array.from(this.memoryStrength),
            timestamp: Date.now()
        };
    }
    
    importMemoryState(memoryData) {
        this.attractorMemory.set(memoryData.attractorMemory);
        this.memoryStrength.set(memoryData.memoryStrength);
    }
}

// Enhanced Scout with Memory and Dreaming Behavior
class DreamingScout {
    constructor(type) {
        this.type = type;
        this.x = Math.random() * FIELD_SIZE;
        this.y = Math.random() * FIELD_SIZE;
        this.vx = 0;
        this.vy = 0;
        this.activation = 0;
        this.age = 0;
        this.energy = Math.random() * 0.5 + 0.5;
        this.sensitivity = Math.random() * 0.5 + 0.5;
        this.threshold = Math.random() * 0.3 + 0.1;
        
        // Memory and dreaming properties
        this.memory = new Float32Array(10); // Short-term memory of past activations
        this.memoryIndex = 0;
        this.dreamMode = false;
        this.autonomousDrift = { x: 0, y: 0 };
    }
    
    update(psiField) {
        this.age++;
        this.dreamMode = psiField.isDreaming;
        
        const x = Math.floor(this.x);
        const y = Math.floor(this.y);
        if (x < 0 || x >= psiField.width || y < 0 || y >= psiField.height) return;
        
        const idx = y * psiField.width + x;
        
        // Get stimulus based on scout type
        let stimulus = 0;
        let fx = 0, fy = 0;
        
        if (this.dreamMode) {
            // In dream mode, scouts respond to memory patterns and drift autonomously
            stimulus = this.getDreamStimulus(psiField, x, y);
            this.updateAutonomousDrift(psiField);
            fx += this.autonomousDrift.x;
            fy += this.autonomousDrift.y;
        } else {
            // Normal operation - respond to actual visual features
            stimulus = this.getVisualStimulus(psiField, x, y);
        }
        
        // Update memory
        this.memory[this.memoryIndex] = stimulus;
        this.memoryIndex = (this.memoryIndex + 1) % this.memory.length;
        
        // Activation follows minimodel principle
        this.activation = this.activation * 0.9 + stimulus * this.sensitivity * 0.1;
        
        // Movement based on activation and mode
        if (this.activation > this.threshold) {
            const gradient = this.getGradient(psiField, x, y);
            fx += gradient.x * this.activation * 5;
            fy += gradient.y * this.activation * 5;
            
            // Clustering behavior
            const clusterForce = this.getClusterForce(psiField);
            fx += clusterForce.x;
            fy += clusterForce.y;
        }
        
        // Add exploration noise (more in dream mode)
        const noiseLevel = this.dreamMode ? 2.0 : 1.0;
        fx += (Math.random() - 0.5) * noiseLevel;
        fy += (Math.random() - 0.5) * noiseLevel;
        
        // Update velocity and position
        this.vx = this.vx * 0.8 + fx * 0.1;
        this.vy = this.vy * 0.8 + fy * 0.1;
        
        this.x += this.vx;
        this.y += this.vy;
        
        // Boundary conditions
        this.x = Math.max(5, Math.min(FIELD_SIZE - 5, this.x));
        this.y = Math.max(5, Math.min(FIELD_SIZE - 5, this.y));
        
        // Energy dynamics
        this.energy = this.energy * 0.99 + this.activation * 0.01;
    }
    
    getDreamStimulus(field, x, y) {
        const idx = y * field.width + x;
        // In dream mode, respond to memory patterns and evolving attractors
        const memoryStrength = field.memoryStrength[idx];
        const memoryContent = field.attractorMemory[idx];
        
        // Add some randomness for autonomous evolution
        const noise = (Math.random() - 0.5) * 0.2;
        
        return memoryStrength * memoryContent + noise;
    }
    
    getVisualStimulus(field, x, y) {
        // Normal visual feature detection (same as before)
        switch (this.type) {
            case SCOUT_TYPES.EDGE_VERTICAL:
                return this.getVerticalEdge(field, x, y);
            case SCOUT_TYPES.EDGE_HORIZONTAL:
                return this.getHorizontalEdge(field, x, y);
            case SCOUT_TYPES.EDGE_DIAGONAL_1:
                return this.getDiagonalEdge1(field, x, y);
            case SCOUT_TYPES.EDGE_DIAGONAL_2:
                return this.getDiagonalEdge2(field, x, y);
            case SCOUT_TYPES.MOTION_UP:
            case SCOUT_TYPES.MOTION_DOWN:
            case SCOUT_TYPES.MOTION_LEFT:
            case SCOUT_TYPES.MOTION_RIGHT:
                const idx = y * field.width + x;
                return field.motionMap[idx];
            case SCOUT_TYPES.COLOR_BRIGHT:
                return field.colorMap[y * field.width + x];
            case SCOUT_TYPES.COLOR_DARK:
                return 1.0 - field.colorMap[y * field.width + x];
            case SCOUT_TYPES.TEXTURE_HIGH:
                return field.textureMap[y * field.width + x];
            case SCOUT_TYPES.TEXTURE_LOW:
                return Math.max(0, 0.5 - field.textureMap[y * field.width + x]);
            default:
                return 0;
        }
    }
    
    updateAutonomousDrift(field) {
        // In dream mode, scouts drift based on memory patterns
        const time = Date.now() * 0.001;
        this.autonomousDrift.x = Math.sin(time * 0.1 + this.x * 0.01) * 0.5;
        this.autonomousDrift.y = Math.cos(time * 0.1 + this.y * 0.01) * 0.5;
    }
    
    // ... (include all the edge detection methods from before)
    getVerticalEdge(field, x, y) {
        if (x <= 0 || x >= field.width - 1) return 0;
        const idx = y * field.width + x;
        return Math.abs(field.current[idx - 1] - field.current[idx + 1]);
    }
    
    getHorizontalEdge(field, x, y) {
        if (y <= 0 || y >= field.height - 1) return 0;
        const idx = y * field.width + x;
        return Math.abs(field.current[idx - field.width] - field.current[idx + field.width]);
    }
    
    getDiagonalEdge1(field, x, y) {
        if (x <= 0 || x >= field.width - 1 || y <= 0 || y >= field.height - 1) return 0;
        const idx = y * field.width + x;
        return Math.abs(field.current[idx - field.width - 1] - field.current[idx + field.width + 1]);
    }
    
    getDiagonalEdge2(field, x, y) {
        if (x <= 0 || x >= field.width - 1 || y <= 0 || y >= field.height - 1) return 0;
        const idx = y * field.width + x;
        return Math.abs(field.current[idx - field.width + 1] - field.current[idx + field.width - 1]);
    }
    
    getGradient(field, x, y) {
        let gx = 0, gy = 0;
        
        const targetMap = this.dreamMode ? field.attractorMemory : 
            (this.type <= 3) ? field.edgeMap : 
            (this.type <= 7) ? field.motionMap : field.colorMap;
        
        if (x > 0 && x < field.width - 1) {
            gx = targetMap[(y * field.width) + x + 1] - targetMap[(y * field.width) + x - 1];
        }
        if (y > 0 && y < field.height - 1) {
            gy = targetMap[((y + 1) * field.width) + x] - targetMap[((y - 1) * field.width) + x];
        }
        
        return { x: gx, y: gy };
    }
    
    getClusterForce(field) {
        const x = Math.floor(this.x);
        const y = Math.floor(this.y);
        let fx = 0, fy = 0;
        
        if (x > 0 && x < field.width - 1 && y > 0 && y < field.height - 1) {
            const idx = y * field.width + x;
            const targetField = this.dreamMode ? field.attractorMemory : field.attractorField;
            fx = (targetField[idx + 1] - targetField[idx - 1]) * 2;
            fy = (targetField[idx + field.width] - targetField[idx - field.width]) * 2;
        }
        
        return { x: fx, y: fy };
    }
}

// Main Dreaming Intelligence System
const GeometricDreamingIntelligence = () => {
    const [isRunning, setIsRunning] = useState(false);
    const [isDreaming, setIsDreaming] = useState(false);
    const [stats, setStats] = useState({
        activeScouts: 0,
        clusters: 0,
        fieldEnergy: 0,
        coherence: 0,
        memoryStrength: 0,
        dreamIntensity: 0
    });
    const [scoutVisibility, setScoutVisibility] = useState({
        [SCOUT_TYPES.EDGE_VERTICAL]: true,
        [SCOUT_TYPES.EDGE_HORIZONTAL]: true,
        [SCOUT_TYPES.EDGE_DIAGONAL_1]: false,
        [SCOUT_TYPES.EDGE_DIAGONAL_2]: false,
        [SCOUT_TYPES.MOTION_UP]: true,
        [SCOUT_TYPES.MOTION_DOWN]: true,
        [SCOUT_TYPES.MOTION_LEFT]: true,
        [SCOUT_TYPES.MOTION_RIGHT]: true,
        [SCOUT_TYPES.COLOR_BRIGHT]: false,
        [SCOUT_TYPES.COLOR_DARK]: false,
        [SCOUT_TYPES.TEXTURE_HIGH]: true,
        [SCOUT_TYPES.TEXTURE_LOW]: false
    });
    
    const videoRef = useRef(null);
    const inputCanvasRef = useRef(null);
    const fieldCanvasRef = useRef(null);
    const scoutCanvasRef = useRef(null);
    const attractorCanvasRef = useRef(null);
    const memoryCanvasRef = useRef(null);
    const animationRef = useRef(null);
    
    const psiFieldRef = useRef(new DreamingPsiField());
    const scoutsRef = useRef([]);
    
    // Initialize scouts
    useEffect(() => {
        const scouts = [];
        const scoutsPerType = Math.floor(MAX_SCOUTS / ATTRACTOR_TYPES);
        
        Object.values(SCOUT_TYPES).forEach(type => {
            for (let i = 0; i < scoutsPerType; i++) {
                scouts.push(new DreamingScout(type));
            }
        });
        
        scoutsRef.current = scouts;
    }, []);
    
    const startCamera = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: FIELD_SIZE, height: FIELD_SIZE }
            });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
                setIsRunning(true);
            }
        } catch (err) {
            console.error('Camera access failed:', err);
        }
    }, []);
    
    const renderInput = useCallback((ctx, imageData) => {
        ctx.putImageData(imageData, 0, 0);
    }, []);
    
    const renderField = useCallback((ctx) => {
        const field = psiFieldRef.current;
        const imageData = ctx.createImageData(FIELD_SIZE, FIELD_SIZE);
        
        // Render field with dream overlay
        for (let i = 0; i < field.edgeMap.length; i++) {
            let r = Math.min(255, field.edgeMap[i] * 255 * 2);
            let g = Math.min(255, field.motionMap[i] * 255 * 10);
            let b = Math.min(255, field.textureMap[i] * 255 * 5);
            
            // Add dream intensity overlay
            if (field.isDreaming) {
                const dreamOverlay = field.dreamIntensity * 100;
                r = Math.min(255, r + dreamOverlay);
                g = Math.min(255, g);
                b = Math.min(255, b + dreamOverlay);
            }
            
            imageData.data[i * 4] = r;
            imageData.data[i * 4 + 1] = g;
            imageData.data[i * 4 + 2] = b;
            imageData.data[i * 4 + 3] = 255;
        }
        
        ctx.putImageData(imageData, 0, 0);
    }, []);
    
    const renderScouts = useCallback((ctx) => {
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, FIELD_SIZE, FIELD_SIZE);
        
        // Render scouts with dream mode indication
        scoutsRef.current.forEach(scout => {
            if (!scoutVisibility[scout.type] || scout.activation < 0.1) return;
            
            let color = SCOUT_COLORS[scout.type];
            if (scout.dreamMode) {
                // Add purple tint to dreaming scouts
                color = color.replace('#', '#aa');
            }
            
            ctx.fillStyle = color;
            ctx.globalAlpha = Math.min(1.0, scout.activation * 2);
            
            const size = 1 + scout.activation * 3;
            ctx.fillRect(scout.x - size/2, scout.y - size/2, size, size);
        });
        
        ctx.globalAlpha = 1.0;
    }, [scoutVisibility]);
    
    const renderAttractors = useCallback((ctx) => {
        const field = psiFieldRef.current;
        const imageData = ctx.createImageData(FIELD_SIZE, FIELD_SIZE);
        
        // Render current attractor field
        for (let i = 0; i < field.attractorField.length; i++) {
            const intensity = Math.min(255, field.attractorField[i] * 255 * 10);
            
            imageData.data[i * 4] = intensity;
            imageData.data[i * 4 + 1] = intensity;
            imageData.data[i * 4 + 2] = 0;
            imageData.data[i * 4 + 3] = 255;
        }
        
        ctx.putImageData(imageData, 0, 0);
    }, []);
    
    const renderMemory = useCallback((ctx) => {
        const field = psiFieldRef.current;
        const imageData = ctx.createImageData(FIELD_SIZE, FIELD_SIZE);
        
        // Render memory field
        for (let i = 0; i < field.attractorMemory.length; i++) {
            const memoryIntensity = Math.min(255, field.attractorMemory[i] * 255);
            const strengthIntensity = Math.min(255, field.memoryStrength[i] * 255);
            
            imageData.data[i * 4] = memoryIntensity;     // R - Memory content
            imageData.data[i * 4 + 1] = 0;              // G
            imageData.data[i * 4 + 2] = strengthIntensity; // B - Memory strength
            imageData.data[i * 4 + 3] = 255;            // A
        }
        
        ctx.putImageData(imageData, 0, 0);
    }, []);
    
    const animate = useCallback(() => {
        if (!isRunning || !videoRef.current) return;
        
        const video = videoRef.current;
        if (video.readyState >= 2) {
            const inputCtx = inputCanvasRef.current?.getContext('2d');
            const fieldCtx = fieldCanvasRef.current?.getContext('2d');
            const scoutCtx = scoutCanvasRef.current?.getContext('2d');
            const attractorCtx = attractorCanvasRef.current?.getContext('2d');
            const memoryCtx = memoryCanvasRef.current?.getContext('2d');
            
            if (inputCtx && fieldCtx && scoutCtx && attractorCtx && memoryCtx) {
                // Capture frame
                inputCtx.drawImage(video, 0, 0, FIELD_SIZE, FIELD_SIZE);
                const imageData = inputCtx.getImageData(0, 0, FIELD_SIZE, FIELD_SIZE);
                
                // Update psi field (handles dreaming automatically)
                psiFieldRef.current.updateFromImage(imageData);
                
                // Update all scouts
                scoutsRef.current.forEach(scout => {
                    scout.update(psiFieldRef.current);
                });
                
                // Update attractor field
                psiFieldRef.current.updateAttractorField(scoutsRef.current);
                
                // Render all views
                renderInput(inputCtx, imageData);
                renderField(fieldCtx);
                renderScouts(scoutCtx);
                renderAttractors(attractorCtx);
                renderMemory(memoryCtx);
                
                // Update stats and dream state
                const activeScouts = scoutsRef.current.filter(s => s.activation > 0.1).length;
                const fieldEnergy = psiFieldRef.current.attractorField.reduce((sum, val) => sum + val, 0);
                const memoryStrength = psiFieldRef.current.memoryStrength.reduce((sum, val) => sum + val, 0) / psiFieldRef.current.memoryStrength.length;
                
                setIsDreaming(psiFieldRef.current.isDreaming);
                setStats({
                    activeScouts,
                    clusters: Math.floor(activeScouts / 50),
                    fieldEnergy: fieldEnergy.toFixed(2),
                    coherence: (activeScouts / MAX_SCOUTS).toFixed(3),
                    memoryStrength: memoryStrength.toFixed(3),
                    dreamIntensity: psiFieldRef.current.dreamIntensity.toFixed(3)
                });
            }
        }
        
        animationRef.current = requestAnimationFrame(animate);
    }, [isRunning, renderInput, renderField, renderScouts, renderAttractors, renderMemory]);
    
    useEffect(() => {
        if (isRunning) {
            animate();
        } else if (animationRef.current) {
            cancelAnimationFrame(animationRef.current);
        }
        
        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [isRunning, animate]);
    
    const resetSystem = () => {
        psiFieldRef.current = new DreamingPsiField();
        scoutsRef.current.forEach(scout => {
            scout.x = Math.random() * FIELD_SIZE;
            scout.y = Math.random() * FIELD_SIZE;
            scout.vx = 0;
            scout.vy = 0;
            scout.activation = 0;
            scout.energy = Math.random() * 0.5 + 0.5;
            scout.memory.fill(0);
            scout.memoryIndex = 0;
        });
    };
    
    const saveMemory = () => {
        const memoryState = psiFieldRef.current.exportMemoryState();
        const blob = new Blob([JSON.stringify(memoryState)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `memory_state_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };
    
    const loadMemory = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const memoryState = JSON.parse(e.target.result);
                        psiFieldRef.current.importMemoryState(memoryState);
                    } catch (err) {
                        console.error('Failed to load memory:', err);
                    }
                };
                reader.readAsText(file);
            }
        };
        input.click();
    };
    
    return (
        <div className="w-full h-screen bg-black text-white flex flex-col">
            <video ref={videoRef} className="hidden" playsInline muted />
            
            {/* Header */}
            <div className="p-4 bg-gray-900 border-b border-gray-700">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Brain className="text-cyan-400" size={24} />
                        <h1 className="text-xl font-bold">Geometric Dreaming Intelligence</h1>
                        <span className="text-sm text-gray-400">
                            {isDreaming ? '💤 Dreaming' : '👁️ Awake'} • {MAX_SCOUTS} Scouts • Memory VAE
                        </span>
                    </div>
                    
                    <div className="flex items-center gap-4">
                        <div className="text-sm space-x-4">
                            <span>Active: <span className="text-green-400">{stats.activeScouts}</span></span>
                            <span>Memory: <span className="text-purple-400">{stats.memoryStrength}</span></span>
                            <span>Dream: <span className="text-pink-400">{stats.dreamIntensity}</span></span>
                            <span>Coherence: <span className="text-blue-400">{stats.coherence}</span></span>
                        </div>
                        
                        <div className="flex gap-2">
                            {!isRunning ? (
                                <button 
                                    onClick={startCamera}
                                    className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded transition-colors"
                                >
                                    <Video size={16} /> Start Vision
                                </button>
                            ) : (
                                <button 
                                    onClick={() => setIsRunning(false)}
                                    className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded transition-colors"
                                >
                                    <Pause size={16} /> Stop
                                </button>
                            )}
                            
                            <button 
                                onClick={saveMemory}
                                className="flex items-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded transition-colors"
                            >
                                <Save size={16} /> Save Memory
                            </button>
                            
                            <button 
                                onClick={loadMemory}
                                className="flex items-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 rounded transition-colors"
                            >
                                <Upload size={16} /> Load Memory
                            </button>
                            
                            <button 
                                onClick={resetSystem}
                                className="flex items-center gap-2 px-3 py-2 bg-gray-600 hover:bg-gray-700 rounded transition-colors"
                            >
                                <RotateCcw size={16} /> Reset
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            {/* Main Display Grid */}
            <div className="flex-1 grid grid-cols-3 grid-rows-2 gap-2 p-2">
                {/* Input Video */}
                <div className="bg-gray-900 border border-gray-700 rounded flex flex-col">
                    <div className="p-2 border-b border-gray-700">
                        <h3 className="text-cyan-400 font-semibold flex items-center gap-2">
                            <Eye size={16} /> Visual Input (Retina)
                        </h3>
                    </div>
                    <div className="flex-1 flex items-center justify-center">
                        <canvas 
                            ref={inputCanvasRef}
                            width={FIELD_SIZE}
                            height={FIELD_SIZE}
                            className="max-w-full max-h-full border border-gray-600"
                        />
                    </div>
                </div>
                
                {/* Feature Field */}
                <div className="bg-gray-900 border border-gray-700 rounded flex flex-col">
                    <div className="p-2 border-b border-gray-700">
                        <h3 className="text-orange-400 font-semibold flex items-center gap-2">
                            <Layers size={16} /> Feature Field
                        </h3>
                        <div className="text-xs text-gray-400 mt-1">
                            {isDreaming ? 'Dream Mode - Memory Reconstruction' : 'R=Edges G=Motion B=Texture'}
                        </div>
                    </div>
                    <div className="flex-1 flex items-center justify-center">
                        <canvas 
                            ref={fieldCanvasRef}
                            width={FIELD_SIZE}
                            height={FIELD_SIZE}
                            className="max-w-full max-h-full border border-gray-600"
                        />
                    </div>
                </div>
                
                {/* Scout Population */}
                <div className="bg-gray-900 border border-gray-700 rounded flex flex-col">
                    <div className="p-2 border-b border-gray-700">
                        <h3 className="text-purple-400 font-semibold flex items-center gap-2">
                            <Zap size={16} /> Scout Population
                        </h3>
                        <div className="text-xs text-gray-400 mt-1">
                            {isDreaming ? 'Autonomous Dream Exploration' : 'Visual Feature Detection'}
                        </div>
                    </div>
                    <div className="flex-1 flex items-center justify-center">
                        <canvas 
                            ref={scoutCanvasRef}
                            width={FIELD_SIZE}
                            height={FIELD_SIZE}
                            className="max-w-full max-h-full border border-gray-600"
                        />
                    </div>
                </div>
                
                {/* Attractor Field */}
                <div className="bg-gray-900 border border-gray-700 rounded flex flex-col">
                    <div className="p-2 border-b border-gray-700">
                        <h3 className="text-yellow-400 font-semibold flex items-center gap-2">
                            <Brain size={16} /> Active Attractors
                        </h3>
                    </div>
                    <div className="flex-1 flex items-center justify-center">
                        <canvas 
                            ref={attractorCanvasRef}
                            width={FIELD_SIZE}
                            height={FIELD_SIZE}
                            className="max-w-full max-h-full border border-gray-600"
                        />
                    </div>
                </div>
                
                {/* Memory Field */}
                <div className="bg-gray-900 border border-gray-700 rounded flex flex-col">
                    <div className="p-2 border-b border-gray-700">
                        <h3 className="text-pink-400 font-semibold flex items-center gap-2">
                            <Lightbulb size={16} /> Memory Patterns
                        </h3>
                        <div className="text-xs text-gray-400 mt-1">R=Content B=Strength</div>
                    </div>
                    <div className="flex-1 flex items-center justify-center">
                        <canvas 
                            ref={memoryCanvasRef}
                            width={FIELD_SIZE}
                            height={FIELD_SIZE}
                            className="max-w-full max-h-full border border-gray-600"
                        />
                    </div>
                </div>
                
                {/* Instructions/Help */}
                <div className="bg-gray-900 border border-gray-700 rounded flex flex-col">
                    <div className="p-2 border-b border-gray-700">
                        <h3 className="text-green-400 font-semibold">💡 Dream Experiment</h3>
                    </div>
                    <div className="flex-1 p-4 text-sm text-gray-300 overflow-y-auto">
                        <div className="space-y-2">
                            <p><strong>1. Let it learn:</strong> Run with camera visible for 30+ seconds</p>
                            <p><strong>2. Cover camera:</strong> Use tape/hand to block visual input</p>
                            <p><strong>3. Watch it dream:</strong> Observe autonomous attractor evolution</p>
                            <p><strong>4. Save/Load:</strong> Export memory states for later</p>
                            <hr className="border-gray-600" />
                            <p className="text-xs text-gray-400">
                                The system builds geometric memories of your visual environment. 
                                When input is blocked, it enters dream mode where attractors 
                                evolve autonomously based on learned patterns.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
            
            {/* Scout Control Panel */}
            <div className="p-4 bg-gray-800 border-t border-gray-700">
                <div className="grid grid-cols-6 gap-2 text-xs">
                    {Object.entries(SCOUT_TYPES).map(([name, type]) => (
                        <label key={type} className="flex items-center gap-2 cursor-pointer p-2 rounded hover:bg-gray-700">
                            <input 
                                type="checkbox" 
                                checked={scoutVisibility[type]} 
                                onChange={() => setScoutVisibility(prev => ({...prev, [type]: !prev[type]}))}
                                className="form-checkbox h-3 w-3 accent-cyan-400"
                            />
                            <div 
                                className="w-3 h-3 rounded" 
                                style={{ backgroundColor: SCOUT_COLORS[type] }}
                            />
                            <span className="text-gray-300">{name.replace('_', ' ')}</span>
                        </label>
                    ))}
                </div>
            </div>
            
            {/* Status Footer */}
            <div className="p-2 bg-gray-800 border-t border-gray-700 text-xs text-gray-400">
                {isRunning ? 
                    `🟢 ${isDreaming ? 'DREAMING' : 'AWAKE'} - ${stats.activeScouts}/${MAX_SCOUTS} scouts • Memory Strength: ${stats.memoryStrength} • Dream Intensity: ${stats.dreamIntensity}` : 
                    "🔴 System Inactive - Start Vision to begin geometric intelligence with memory formation"
                }
            </div>
        </div>
    );
};

export default GeometricDreamingIntelligence;