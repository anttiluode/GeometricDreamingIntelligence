import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Brain, Play, Pause, RotateCcw, Download, Video, Layers, Zap, Eye } from 'lucide-react';

const FIELD_SIZE = 256;
const MAX_SCOUTS = 8000; // Massively parallel like V1!
const ATTRACTOR_TYPES = 12; // Many different minimodel types

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

// The Psi Field - Our shared "retina" driven by webcam
class PsiField {
    constructor() {
        this.width = FIELD_SIZE;
        this.height = FIELD_SIZE;
        this.current = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.previous = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.history = [];
        this.maxHistory = 5;
        
        // Feature maps - the "core layer" like Layer 1 in the paper
        this.edgeMap = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.motionMap = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.colorMap = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        this.textureMap = new Float32Array(FIELD_SIZE * FIELD_SIZE);
        
        // Attractor field - emergent from scout collective
        this.attractorField = new Float32Array(FIELD_SIZE * FIELD_SIZE);
    }
    
    updateFromImage(imageData) {
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
        
        this.computeFeatureMaps();
    }
    
    computeFeatureMaps() {
        // Edge detection (core layer processing)
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
                
                // Motion detection
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
        
        // Each scout contributes to the field based on its activation
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
}

// Individual Scout - A "minimodel" like individual V1 neurons
class Scout {
    constructor(type) {
        this.type = type;
        this.x = Math.random() * FIELD_SIZE;
        this.y = Math.random() * FIELD_SIZE;
        this.vx = 0;
        this.vy = 0;
        this.activation = 0;
        this.age = 0;
        this.clusterId = -1;
        this.energy = Math.random() * 0.5 + 0.5;
        
        // Each scout has its own "readout weights" like the paper
        this.sensitivity = Math.random() * 0.5 + 0.5;
        this.threshold = Math.random() * 0.3 + 0.1;
    }
    
    update(psiField) {
        this.age++;
        
        const x = Math.floor(this.x);
        const y = Math.floor(this.y);
        if (x < 0 || x >= psiField.width || y < 0 || y >= psiField.height) return;
        
        const idx = y * psiField.width + x;
        
        // Each scout type responds to different features (minimodel specificity)
        let stimulus = 0;
        let fx = 0, fy = 0;
        
        switch (this.type) {
            case SCOUT_TYPES.EDGE_VERTICAL:
                stimulus = this.getVerticalEdge(psiField, x, y);
                break;
            case SCOUT_TYPES.EDGE_HORIZONTAL:
                stimulus = this.getHorizontalEdge(psiField, x, y);
                break;
            case SCOUT_TYPES.EDGE_DIAGONAL_1:
                stimulus = this.getDiagonalEdge1(psiField, x, y);
                break;
            case SCOUT_TYPES.EDGE_DIAGONAL_2:
                stimulus = this.getDiagonalEdge2(psiField, x, y);
                break;
            case SCOUT_TYPES.MOTION_UP:
            case SCOUT_TYPES.MOTION_DOWN:
            case SCOUT_TYPES.MOTION_LEFT:
            case SCOUT_TYPES.MOTION_RIGHT:
                stimulus = psiField.motionMap[idx];
                break;
            case SCOUT_TYPES.COLOR_BRIGHT:
                stimulus = psiField.colorMap[idx];
                break;
            case SCOUT_TYPES.COLOR_DARK:
                stimulus = 1.0 - psiField.colorMap[idx];
                break;
            case SCOUT_TYPES.TEXTURE_HIGH:
                stimulus = psiField.textureMap[idx];
                break;
            case SCOUT_TYPES.TEXTURE_LOW:
                stimulus = Math.max(0, 0.5 - psiField.textureMap[idx]);
                break;
        }
        
        // Activation follows the minimodel principle: simple weighted sum
        this.activation = this.activation * 0.9 + stimulus * this.sensitivity * 0.1;
        
        // Movement based on gradient following (like neural hill climbing)
        if (this.activation > this.threshold) {
            const gradient = this.getGradient(psiField, x, y);
            fx = gradient.x * this.activation * 5;
            fy = gradient.y * this.activation * 5;
            
            // Add attraction to other active scouts of same type (clustering)
            const clusterForce = this.getClusterForce(psiField);
            fx += clusterForce.x;
            fy += clusterForce.y;
        }
        
        // Add some exploration noise
        fx += (Math.random() - 0.5) * 1.0;
        fy += (Math.random() - 0.5) * 1.0;
        
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
        
        switch (this.type) {
            case SCOUT_TYPES.EDGE_VERTICAL:
            case SCOUT_TYPES.EDGE_HORIZONTAL:
            case SCOUT_TYPES.EDGE_DIAGONAL_1:
            case SCOUT_TYPES.EDGE_DIAGONAL_2:
                if (x > 0 && x < field.width - 1) {
                    gx = field.edgeMap[(y * field.width) + x + 1] - field.edgeMap[(y * field.width) + x - 1];
                }
                if (y > 0 && y < field.height - 1) {
                    gy = field.edgeMap[((y + 1) * field.width) + x] - field.edgeMap[((y - 1) * field.width) + x];
                }
                break;
            case SCOUT_TYPES.MOTION_UP:
            case SCOUT_TYPES.MOTION_DOWN:
            case SCOUT_TYPES.MOTION_LEFT:
            case SCOUT_TYPES.MOTION_RIGHT:
                if (x > 0 && x < field.width - 1) {
                    gx = field.motionMap[(y * field.width) + x + 1] - field.motionMap[(y * field.width) + x - 1];
                }
                if (y > 0 && y < field.height - 1) {
                    gy = field.motionMap[((y + 1) * field.width) + x] - field.motionMap[((y - 1) * field.width) + x];
                }
                break;
            default:
                if (x > 0 && x < field.width - 1) {
                    gx = field.colorMap[(y * field.width) + x + 1] - field.colorMap[(y * field.width) + x - 1];
                }
                if (y > 0 && y < field.height - 1) {
                    gy = field.colorMap[((y + 1) * field.width) + x] - field.colorMap[((y - 1) * field.width) + x];
                }
                break;
        }
        
        return { x: gx, y: gy };
    }
    
    getClusterForce(field) {
        // Simplified clustering - attract to attractor field
        const x = Math.floor(this.x);
        const y = Math.floor(this.y);
        let fx = 0, fy = 0;
        
        if (x > 0 && x < field.width - 1 && y > 0 && y < field.height - 1) {
            const idx = y * field.width + x;
            fx = (field.attractorField[idx + 1] - field.attractorField[idx - 1]) * 2;
            fy = (field.attractorField[idx + field.width] - field.attractorField[idx - field.width]) * 2;
        }
        
        return { x: fx, y: fy };
    }
}

// Main Intelligence System
const MassivelyParallelGeometricIntelligence = () => {
    const [isRunning, setIsRunning] = useState(false);
    const [stats, setStats] = useState({
        activeScouts: 0,
        clusters: 0,
        fieldEnergy: 0,
        coherence: 0
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
    const animationRef = useRef(null);
    
    const psiFieldRef = useRef(new PsiField());
    const scoutsRef = useRef([]);
    
    // Initialize scouts
    useEffect(() => {
        const scouts = [];
        const scoutsPerType = Math.floor(MAX_SCOUTS / ATTRACTOR_TYPES);
        
        Object.values(SCOUT_TYPES).forEach(type => {
            for (let i = 0; i < scoutsPerType; i++) {
                scouts.push(new Scout(type));
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
        
        // Render edge map in red channel, motion in green, texture in blue
        for (let i = 0; i < field.edgeMap.length; i++) {
            const edge = Math.min(255, field.edgeMap[i] * 255 * 2);
            const motion = Math.min(255, field.motionMap[i] * 255 * 10);
            const texture = Math.min(255, field.textureMap[i] * 255 * 5);
            
            imageData.data[i * 4] = edge;         // R - edges
            imageData.data[i * 4 + 1] = motion;   // G - motion
            imageData.data[i * 4 + 2] = texture;  // B - texture
            imageData.data[i * 4 + 3] = 255;      // A
        }
        
        ctx.putImageData(imageData, 0, 0);
    }, []);
    
    const renderScouts = useCallback((ctx) => {
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, FIELD_SIZE, FIELD_SIZE);
        
        // Render scouts by type
        scoutsRef.current.forEach(scout => {
            if (!scoutVisibility[scout.type] || scout.activation < 0.1) return;
            
            ctx.fillStyle = SCOUT_COLORS[scout.type];
            ctx.globalAlpha = Math.min(1.0, scout.activation * 2);
            
            const size = 1 + scout.activation * 2;
            ctx.fillRect(scout.x - size/2, scout.y - size/2, size, size);
        });
        
        ctx.globalAlpha = 1.0;
    }, [scoutVisibility]);
    
    const renderAttractors = useCallback((ctx) => {
        const field = psiFieldRef.current;
        const imageData = ctx.createImageData(FIELD_SIZE, FIELD_SIZE);
        
        // Render attractor field
        for (let i = 0; i < field.attractorField.length; i++) {
            const intensity = Math.min(255, field.attractorField[i] * 255 * 10);
            
            imageData.data[i * 4] = intensity;     // R
            imageData.data[i * 4 + 1] = intensity; // G
            imageData.data[i * 4 + 2] = 0;         // B
            imageData.data[i * 4 + 3] = 255;       // A
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
            
            if (inputCtx && fieldCtx && scoutCtx && attractorCtx) {
                // Capture frame
                inputCtx.drawImage(video, 0, 0, FIELD_SIZE, FIELD_SIZE);
                const imageData = inputCtx.getImageData(0, 0, FIELD_SIZE, FIELD_SIZE);
                
                // Update psi field from webcam
                psiFieldRef.current.updateFromImage(imageData);
                
                // Update all scouts (massively parallel minimodels)
                scoutsRef.current.forEach(scout => {
                    scout.update(psiFieldRef.current);
                });
                
                // Update attractor field from scout collective
                psiFieldRef.current.updateAttractorField(scoutsRef.current);
                
                // Render all views
                renderInput(inputCtx, imageData);
                renderField(fieldCtx);
                renderScouts(scoutCtx);
                renderAttractors(attractorCtx);
                
                // Update stats
                const activeScouts = scoutsRef.current.filter(s => s.activation > 0.1).length;
                const fieldEnergy = psiFieldRef.current.attractorField.reduce((sum, val) => sum + val, 0);
                
                setStats({
                    activeScouts,
                    clusters: Math.floor(activeScouts / 50), // Rough estimate
                    fieldEnergy: fieldEnergy.toFixed(2),
                    coherence: (activeScouts / MAX_SCOUTS).toFixed(3)
                });
            }
        }
        
        animationRef.current = requestAnimationFrame(animate);
    }, [isRunning, renderInput, renderField, renderScouts, renderAttractors]);
    
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
        scoutsRef.current.forEach(scout => {
            scout.x = Math.random() * FIELD_SIZE;
            scout.y = Math.random() * FIELD_SIZE;
            scout.vx = 0;
            scout.vy = 0;
            scout.activation = 0;
            scout.energy = Math.random() * 0.5 + 0.5;
        });
    };
    
    return (
        <div className="w-full h-screen bg-black text-white flex flex-col">
            <video ref={videoRef} className="hidden" playsInline muted />
            
            {/* Header */}
            <div className="p-4 bg-gray-900 border-b border-gray-700">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Brain className="text-cyan-400" size={24} />
                        <h1 className="text-xl font-bold">Massively Parallel Geometric Intelligence</h1>
                        <span className="text-sm text-gray-400">Living Cortex • {MAX_SCOUTS} Minimodel Scouts</span>
                    </div>
                    
                    <div className="flex items-center gap-4">
                        <div className="text-sm space-x-4">
                            <span>Active: <span className="text-green-400">{stats.activeScouts}</span></span>
                            <span>Clusters: <span className="text-yellow-400">{stats.clusters}</span></span>
                            <span>Field Energy: <span className="text-red-400">{stats.fieldEnergy}</span></span>
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
                                onClick={resetSystem}
                                className="flex items-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded transition-colors"
                            >
                                <RotateCcw size={16} /> Reset Scouts
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            {/* Main Display Grid */}
            <div className="flex-1 grid grid-cols-2 grid-rows-2 gap-2 p-2">
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
                            <Layers size={16} /> Feature Field (Core Layer)
                        </h3>
                        <div className="text-xs text-gray-400 mt-1">R=Edges G=Motion B=Texture</div>
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
                            <Zap size={16} /> Scout Population (Minimodels)
                        </h3>
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
                            <Brain size={16} /> Emergent Consciousness (Attractors)
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
                    `🟢 Living Cortex Active - ${stats.activeScouts}/${MAX_SCOUTS} scouts processing visual field through ${ATTRACTOR_TYPES} minimodel types` : 
                    "🔴 Cortex Inactive - Start Vision to activate massively parallel geometric intelligence"
                }
            </div>
        </div>
    );
};

export default MassivelyParallelGeometricIntelligence;