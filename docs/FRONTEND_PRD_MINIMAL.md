# GigVault Frontend — Minimalist PRD (11 Core Pages)

**For:** GigVault Frontend Team / AI Coding Agents  
**Version:** 1.0  
**Date:** 2026-05-11  
**Scope:** A build-ready PRD for the frontend UI covering the 11 core pages mapped to the backend API.

---

## 0) Product Summary

GigVault is a two-sided marketplace for **Musicians/Bands** and **Venue Owners** to:
- post and browse gigs,
- apply and manage applications,
- finalize bookings/contracts,
- manage availability,
- manage setlists for gigs,
- track/record payments,
- post/browse recruitment ads,
- leave reviews and file disputes,
- and provide admins a moderation & analytics dashboard.

This PRD is optimized to be handed to an AI agent to build the frontend.

---

## 1) Assumptions & Non-Goals

### Assumptions
- Backend is reachable at:
  - `http://localhost:5000/api/v1`
- Auth uses JWT:
  - `Authorization: Bearer <access_token>`
- Roles:
  - `MUSICIAN`, `VENUE_OWNER`, `ADMIN`

### Non-Goals (for MVP)
- Real-time chat/messaging
- Payment processor integration (Stripe, etc.) — payments are recorded via backend endpoints
- Advanced analytics beyond what admin dashboard returns

---

## 2) Recommended Frontend Tech Stack

You can change this, but the UI spec below assumes a modern SPA:
- **Framework:** React + TypeScript (Next.js recommended)
- **Styling:** TailwindCSS (or MUI)
- **Forms:** React Hook Form + Zod validation
- **State/Data:** TanStack Query (React Query)
- **Routing:** Next.js App Router or React Router
- **Auth storage:** access token in memory + refresh token in httpOnly cookie (ideal) OR localStorage (simpler)

---

## 3) Global UX Requirements

### 3.1 Navigation
- Top nav:
  - Logo → Dashboard
  - Browse Gigs
  - Bands (musicians only)
  - Recruitment Ads
  - Payments
  - Calendar
  - Admin (admin only)
  - Profile dropdown (Profile, Logout)

### 3.2 Layout
- Responsive:
  - Mobile: stacked cards, bottom nav optional
  - Desktop: left sidebar optional + content

### 3.3 Loading / Empty / Error States
- Each page must include:
  - Skeleton loading state
  - Empty state call-to-action
  - Error state with retry

### 3.4 Toast Notifications
- Success toast on create/update/delete
- Error toast with backend error message

### 3.5 Form Validation
- Match backend constraints (e.g., password min length, rating 1–5)
- Show field-level errors

---

## 4) Security & Access Control (Frontend)

### 4.1 Route Guards
- Unauthenticated users can only access:
  - Auth page (Register/Login)
- Authenticated users:
  - Can access their role-allowed routes
- Admin-only:
  - Admin Dashboard
  - Dispute resolution and moderation sections

### 4.2 Token Handling
- Store tokens and attach access token to every API request
- If 401 occurs:
  - attempt refresh (`POST /auth/refresh`)
  - retry original request once
  - if refresh fails → logout and redirect to login

---

## 5) Data Models (Frontend Types)

Define these as TypeScript interfaces (minimum needed fields):

- `User`: `{ user_id, email, name, role, city?, bio?, profile_pic?, instruments? }`
- `Band`: `{ band_id, name, description?, genres?, members? }`
- `Gig`: `{ gig_id, title, description?, date, end_time?, city, location_details?, genres?, pay_amount, status }`
- `Application`: `{ application_id, gig_id, band_id, status, applied_at?, updated_at? }`
- `Booking`: `{ booking_id, gig_id, band_id, pay_total, deposit_amount?, final_payment?, status, band_signed_at?, venue_signed_at? }`
- `AvailabilityItem`: `{ availability_id?, date, reason, notes? }`
- `Setlist`: `{ setlist_id, band_id, name, gig_id?, songs?, total_duration? }`
- `SetlistSong`: `{ song_id, title, artist?, duration_minutes, order }`
- `Payment`: `{ payment_id, booking_id, amount, payment_type, status, due_date?, paid_date? }`
- `RecruitmentAd`: `{ ad_id, title, description?, instruments_needed, genres?, city, posted_at }`
- `Review`: `{ review_id, booking_id, rating, comment?, created_at }`
- `Dispute`: `{ dispute_id, booking_id, reason, description, status, created_at, resolved_at? }`

---

## 6) API Client Requirements

Create a single API client module with:
- Base URL: `process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:5000/api/v1"`
- Request wrapper:
  - Adds `Authorization` header if token exists
  - Normalizes errors to `{ code, message }`

---

## 7) Pages (11 Core Pages)

Each page below includes:
- Purpose
- Route
- Role access
- UI sections/components
- API calls required
- Primary user flows


# Page 1 — Register / Login / Profile

## Route(s)
- `/auth` (Login/Register)
- `/profile` (View/Edit)

## Roles
- Auth page: public
- Profile: authenticated (all roles)

## UI Components
### Auth (Tabbed)
- Login form: email, password
- Register form: name, email, password, role (MUSICIAN|VENUE_OWNER), city(optional), bio(optional)
- CTA buttons, validation messages

### Profile
- Profile header (avatar, name, role)
- Editable fields: name, city, bio, profile_pic
- Musicians only: instruments multi-select
- Save button + success toast

## API Calls
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /users/{id}`
- `PUT /users/{id}`

## Flows
- Register → auto-login (optional) → redirect dashboard
- Login → store token(s) → redirect dashboard
- Edit profile → optimistic UI optional → refresh user cache


# Page 2 — My Dashboard

## Route
- `/dashboard`

## Roles
- Authenticated (all roles), content changes by role

## UI Components
- Stats cards (counts, rating, pending payments)
- Upcoming gigs list
- Pending applications list
- Pending payments list
- Quick actions:
  - Musicians: Create band, Browse gigs
  - Venue owners: Post gig
  - Admin: Go to admin dashboard

## API Calls
- `GET /users/{id}/dashboard`

(Optionally also call these if backend supports them distinctly; mapping mentions them but backend PRD centralizes dashboard.)

## Flows
- On load fetch dashboard data
- Clicking items navigates to relevant details pages (gig details, booking details, payments)


# Page 3 — Bands List / Band Profile (+ Members)

## Routes
- `/bands` (list)
- `/bands/{band_id}` (profile)

## Roles
- MUSICIAN only

## UI Components
### Bands List
- "Create Band" button
- Band cards/table with name, genres, member count

### Band Profile
- Band info (name, description, genres)
- Edit band modal
- Members list (name, instruments)
- Add member modal (search/select user_id, instruments)
- Remove member action

## API Calls
- `GET /bands?user_id={id}`
- `POST /bands`
- `GET /bands/{id}`
- `PUT /bands/{id}`
- `POST /bands/{id}/members`
- `DELETE /bands/{id}/members/{member_id}`

## Flows
- Create band → redirect to band profile
- Add/remove members updates members list


# Page 4 — Browse Gigs / Search

## Route
- `/gigs`

## Roles
- Authenticated (all roles)

## UI Components
- Filters panel:
  - city, genre, date range, pay range, status (default OPEN), sort
- Search bar (title/description)
- Results list with gig cards
- Pagination controls

## API Calls
- `GET /gigs/browse` with query params
- `GET /gigs/{id}` (prefetch on hover optional)

## Flows
- Adjust filters → refetch list
- Click gig → go to gig details page


# Page 5 — Gig Details / Apply / Applications

## Route
- `/gigs/{gig_id}`

## Roles
- All authenticated

## UI Components
- Gig details section
- Musicians:
  - "Apply" card: choose band (dropdown), submit
  - "My application status" section (if applied)
  - Withdraw button (if allowed)
- Venue owners (if gig belongs to them):
  - Applications table with status chips
  - Actions: shortlist / accept / reject

## API Calls
- `GET /gigs/{id}`
- `POST /applications`
- `GET /applications?gig_id={gig_id}` (mapping shows `/gigs/{id}/applications`; backend PRD defines `/applications` list. Use whichever backend implements.)
- `PUT /applications/{id}`
- `PUT /applications/{id}/withdraw`

## Flows
- Apply → success toast → show status
- Venue owner accepts → UI updates application list; show that gig status becomes BOOKED if backend does so


# Page 6 — Booking & Calendar / Availability

## Route
- `/calendar`

## Roles
- Authenticated (all roles)

## UI Components
- Calendar month view
- Busy dates highlighted (booked/blocked)
- Right panel:
  - Selected date details
  - "Block date" form (reason, notes)
  - "Unblock" button for blocked entries
- Bookings list/table
- Booking details drawer/modal:
  - contract status
  - sign button (if pending)

## API Calls
- `GET /bookings?user_id={id}`
- `GET /bookings/{id}`
- `PUT /bookings/{id}/sign`
- `GET /availability/{user_id}`
- `POST /availability`
- `DELETE /availability/{id}`

## Flows
- Load calendar + bookings
- Block date → calendar refresh
- Sign booking → status updates


# Page 7 — Setlists & Songs

## Routes
- `/setlists` (optional index)
- `/bands/{band_id}/setlists`
- `/setlists/{setlist_id}`

## Roles
- MUSICIAN (band members)

## UI Components
- Setlists list for band
- Create setlist modal
- Setlist details:
  - name + edit
  - songs table
  - add song form
  - reorder songs (drag-and-drop or up/down)
  - delete song
  - delete setlist
  - show total duration

## API Calls
- `GET /bands/{band_id}/setlists`
- `POST /setlists`
- `GET /setlists/{id}`
- `PUT /setlists/{id}`
- `DELETE /setlists/{id}`
- `POST /setlists/{id}/songs`
- `PUT /setlists/{id}/songs/{song_id}`
- `DELETE /setlists/{id}/songs/{song_id}`

## Flows
- Create → open setlist
- Add/reorder/remove songs updates total duration


# Page 8 — Payments Overview

## Route
- `/payments`

## Roles
- Authenticated (all roles)

## UI Components
- Filters: status, date range, booking_id
- Payments list/table
- Payment details drawer
- Venue owner only:
  - "Record Payment" modal: booking_id, amount, type, paid_date
  - Update payment status

## API Calls
- `GET /payments?user_id={id}&status=...`
- `GET /payments/{id}`
- `POST /payments` (venue owner)
- `PUT /payments/{id}` (venue owner)

## Flows
- Record payment → refresh list
- Clicking payment → details view


# Page 9 — Recruitment Ads + Filtering

## Route
- `/recruitment-ads`

## Roles
- Authenticated (all roles), create/edit/delete = musician

## UI Components
- Filters: instrument, genre, city, search, sort
- Ads list with cards
- Ad details modal/page
- Musician actions:
  - Create ad form
  - Edit own ad
  - Delete own ad

## API Calls
- `GET /recruitment-ads/browse`
- `GET /recruitment-ads/{id}`
- `POST /recruitment-ads`
- `PUT /recruitment-ads/{id}`
- `DELETE /recruitment-ads/{id}`

## Flows
- Create ad → appear in list
- Filter → refetch


# Page 10 — Reviews & Disputes

## Route
- `/reviews-disputes`

## Roles
- Authenticated for personal reviews/disputes
- Admin for moderation & dispute resolution sections

## UI Components
- Tabs:
  - "My Reviews" (received/given)
  - "Leave Review" (form: booking_id, rating, comment)
  - "My Disputes" (list + details)
  - "File Dispute" (form)
  - Admin-only: "All Disputes" (resolve)

## API Calls
- `POST /reviews`
- `GET /reviews/{id}` (optional)
- `GET /reviews?user_id={id}`
- (Optional) `GET /reviews?author_id={id}` if backend supports
- `POST /disputes`
- `GET /disputes/{id}`
- `GET /disputes?user_id={id}`
- Admin:
  - `GET /admin/disputes`
  - `PUT /admin/disputes/{id}`

## Flows
- Leave review after completed booking
- File dispute with evidence URLs
- Admin resolves dispute


# Page 11 — Admin Dashboard

## Route
- `/admin`

## Roles
- ADMIN only

## UI Components
- KPI cards: total users, active gigs, bookings, platform revenue, pending disputes
- Users management:
  - filters by role/status/search
  - user table
  - ban/unban + role change
  - reset password modal
- Gigs moderation:
  - gigs list + delete action
- Disputes moderation:
  - list + resolve action

## API Calls
- `GET /admin/dashboard`
- `GET /admin/users`
- `PUT /admin/users/{id}`
- `POST /admin/users/{id}/reset-password`
- `GET /admin/gigs`
- `DELETE /admin/gigs/{id}`
- `GET /admin/disputes`
- `PUT /admin/disputes/{id}`

## Flows
- Admin reviews metrics → manages users/gigs/disputes

---

## 8) Component Inventory (Suggested)

- `AppLayout`, `AuthGuard`, `RoleGuard`
- `ApiClient` + `useAuth`
- `DataTable`, `CardList`, `EmptyState`, `ErrorState`, `Skeleton`
- `GigCard`, `BandCard`, `PaymentRow`, `ApplicationRow`
- `CalendarView`
- Modals:
  - CreateBandModal, EditBandModal, AddMemberModal
  - CreateGigModal (if you later add a post-gig page)
  - RecordPaymentModal
  - CreateRecruitmentAdModal

---

## 9) Acceptance Criteria (MVP)

- All 11 pages exist and are navigable
- Auth works end-to-end:
  - login/register/logout
  - token refresh on 401
- Role-based routing enforced
- Each page implements its required API calls and displays:
  - loading + error + empty states
- CRUD flows:
  - bands, applications, availability, setlists/songs, recruitment ads, payments
- Admin can manage users/gigs/disputes

---

## 10) Open Questions / Backend Alignment Notes

Some endpoints appear in the mapping doc but may not exist exactly as written in backend PRD:
- Mapping references `/gigs/{id}/applications` and `/setlists/{id}/songs` GET.
- Backend PRD centralizes list access via `/applications` and embeds songs in `/setlists/{id}`.

**Frontend guideline:** implement against what the backend actually exposes. If uncertain, prefer these patterns:
- list applications: `GET /applications?gig_id=...`
- setlist songs: rely on `GET /setlists/{id}` returning `songs[]`

---

## Reference Documents
- Frontend→Backend mapping:
  - `docs/FRONTEND_TO_BACKEND_MAPPING.md`
- Backend API PRD:
  - `docs/BACKEND_API_PRD_MINIMAL.md`
