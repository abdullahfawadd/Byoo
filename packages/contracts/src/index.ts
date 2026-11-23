export const sectors = [
  { id: "G-9", label: "G-9", lat: 33.6875, lng: 73.0357, density: "HIGH" },
  { id: "G-10", label: "G-10", lat: 33.6789, lng: 73.0145, density: "HIGH" },
  { id: "G-11", label: "G-11", lat: 33.6677, lng: 72.9996, density: "HIGH" },
  { id: "F-10", label: "F-10", lat: 33.6962, lng: 73.0135, density: "MEDIUM" },
  { id: "I-8", label: "I-8", lat: 33.6730, lng: 73.0832, density: "HIGH" },
  { id: "F-7", label: "F-7", lat: 33.7220, lng: 73.0562, density: "MEDIUM" },
  { id: "F-8", label: "F-8", lat: 33.7131, lng: 73.0374, density: "MEDIUM" },
  { id: "E-11", label: "E-11", lat: 33.7007, lng: 72.9757, density: "LOW" },
  { id: "BLUE_AREA", label: "Blue Area", lat: 33.7148, lng: 73.0690, density: "LOW" },
] as const;

export type Sector = typeof sectors[number]["id"];
export type Role = "CONSUMER" | "LBI_ADMIN" | "PLATFORM_ADMIN";
export type PoolState = "FORMING" | "THRESHOLD_MET" | "LBI_APPROVED" | "DISPATCHED_SIMULATED" | "DELIVERED_AT_HUB" | "COMPLETED" | "CANCELLED_EXPIRED" | "CANCELLED_MAX_RADIUS_UNVIABLE" | "CANCELLED_LBI_REJECTED";
export type LedgerState = "PENDING_CHECKOUT" | "HOLD_SIMULATED" | "RELEASED_SIMULATED" | "REFUNDED_SIMULATED" | "CANCELLED_UNPAID";
export type OrderState = "PLEDGED" | "ESCROW_HELD" | "CANCELLED_CHECKOUT_TIMEOUT" | "CANCELLED_UNPAID" | "READY_FOR_PICKUP" | "COLLECTED";
export type PaymentMethod = "JAZZCASH" | "EASYPAISA";
export type DisputeCategory = "NON_DELIVERY" | "WRONG_PRODUCT" | "QUANTITY_MISMATCH" | "PAYMENT_ISSUE";
export type DisputeResolution = "NO_REFUND" | "FULL_REFUND" | "PARTIAL_REFUND";

export interface User {
  id: string;
  phone: string;
  role: Role;
  name: string | null;
  sector: Sector | null;
  preferences: string[];
}
export interface Category { id: string; name: string; slug: string }
export interface Product {
  id: string;
  sku: string;
  name: string;
  description: string;
  category: Category;
  unit: string;
  retailPrice: number;
  wholesalePrice: number;
  targetMoq: number;
  imageUrl?: string | null;
}
export interface Hub { id: string; name: string; address: string; sector: Sector; lat: number; lng: number; instructions: string }
export interface Pool {
  id: string;
  sector: Sector;
  product: Product;
  hub: Hub;
  lat: number;
  lng: number;
  status: PoolState;
  currentQuantity: number;
  targetMoq: number;
  participants: number;
  radiusKm: number;
  wholesalePrice: number;
  retailPrice: number;
  distanceKm?: number | null;
  healthScore?: number | null;
  createdAt: string;
  expiresAt: string;
  checkoutDeadline: string | null;
  synthetic: boolean;
}
export const PLATFORM_FEE = 4000;

export interface Quote {
  wholesaleSubtotal: number;
  platformFee: number;
  totalPayable: number;
  retailTotal: number;
  grossSavings: number;
  netSavings: number;
}
export function estimateOrder(quantity: number, retailPrice: number, wholesalePrice: number): Quote {
  const retailTotal = quantity * retailPrice;
  const wholesaleSubtotal = quantity * wholesalePrice;
  const totalPayable = wholesaleSubtotal + PLATFORM_FEE;
  return { wholesaleSubtotal, platformFee: PLATFORM_FEE, totalPayable, retailTotal,
    grossSavings: retailTotal - wholesaleSubtotal, netSavings: retailTotal - totalPayable };
}
export function formatPkr(paisa: number): string {
  return `Rs ${new Intl.NumberFormat("en-PK", { maximumFractionDigits: 2 }).format(paisa / 100)}`;
}

export interface Order extends Quote {
  id: string;
  pool: Pool;
  quantity: number;
  status: OrderState;
  ledgerState: LedgerState;
  paymentReference: string | null;
  method: PaymentMethod | null;
  createdAt: string;
  updatedAt: string;
  refundedAmount: number;
}
export interface TrackerEvent { id: string; type: string; label: string; timestamp: string }
export interface Tracker { pool: Pool; events: TrackerEvent[] }
export interface Notification { id: string; type: string; title: string; message: string; poolId: string | null; readAt: string | null; createdAt: string }
export interface Dispute {
  id: string;
  orderId: string;
  poolId: string;
  category: DisputeCategory;
  description: string;
  evidenceUrl: string | null;
  status: "OPEN" | "UNDER_REVIEW" | "RESOLVED";
  notes: string | null;
  resolution: DisputeResolution | null;
  refundAmount: number;
  createdAt: string;
  resolvedAt: string | null;
  consumer?: { id: string; name: string | null };
}
export interface Fulfillment {
  id: string;
  pool: Pool;
  supplier: { id: string; name: string };
  quantity: number;
  status: "CREATED" | "CONFIRMED" | "DISPATCHED" | "AT_HUB" | "SETTLED";
  orders?: { id: string; status: OrderState; quantity: number; consumerName: string | null }[];
  createdAt: string;
}
export interface Dashboard {
  users: number; activePools: number; pendingApprovals: number; completedPools: number;
  cancelledPools: number; orders: number; simulatedVolume: number; consumerSavings: number;
  averageCompletionHours: number | null; sectorDemand: { sector: Sector; quantity: number }[];
  syntheticPools: number;
}
export interface Analytics {
  weekly: { week: string; created: number; completed: number; cancelled: number; registrations: number }[];
  sectors: { sector: Sector; pools: number; quantity: number; averageJoiningVelocity: number; netSavings: number }[];
  products: { sku: string; name: string; quantity: number }[];
  orders: { id: string; poolId: string; status: OrderState; totalPayable: number; createdAt: string }[];
}
export interface AuditRecord { id: string; actorId: string | null; action: string; entityId: string; details: unknown; createdAt: string }
export interface SupplierOffer { id: string; supplierName: string; productName: string; targetMoq: number; wholesalePrice: number; stock: number; lat: number; lng: number; slaRating: number; active: boolean }
export interface LedgerOverview {
  totals: { held: number; released: number; refunded: number; supplier: number; lbi: number; platform: number; residual: number };
  orders: Order[];
}
export interface ModelMetrics {
  rocAuc: number; prAuc: number; precision: number; recall: number; f1: number;
  accuracy: number; brierScore: number; threshold: number;
  confusionMatrix: number[][]; featureImportance: Record<string, number>;
}
export interface AIOverview {
  modelVersion: string | null; datasetVersion: string | null; trainedAt: string | null;
  models: Record<string, ModelMetrics>;
  predictions: { poolId: string; probability: number; modelVersion: string; createdAt: string; outcome?: boolean | null }[];
  decisions: { poolId: string; decision: string; previousRadiusKm: number; proposedRadiusKm: number; finalRadiusKm: number; probability: number; explanation: string; createdAt: string }[];
}
export interface AiFeatures {
  sector: Sector; productSku: string; currentRadiusKm: number; currentQuantity: number;
  targetMoq: number; participantCount: number; joinVelocity: number; recentJoinVelocity: number;
  competingActivePools: number; elapsedHours: number; remainingHours: number;
  radiusExpansionsCount: number; weekday: number; hourOfDay: number;
}
