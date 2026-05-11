# GigVault Backend API — Minimalist PRD

**For:** GigVault Development Team / AI Coding Agents  
**Version:** 1.0  
**Date:** May 2026  
**Scope:** Backend API for 11 core frontend pages covering all database operations

---

# Table of Contents
1. [Overview](#overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [API Endpoints](#api-endpoints)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Indexing & Performance](#indexing--performance)
7. [Deployment & Testing](#deployment--testing)

---

# Overview

## Technology Stack
- **Language:** Python (Flask or FastAPI)
- **Database:** PostgreSQL or MySQL
- **Authentication:** JWT (JSON Web Tokens)
- **API Format:** RESTful JSON

## Base URL
```
http://localhost:5000/api/v1
```

## General Notes
- All timestamps in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- Pagination default: `page=1, limit=10`
- All list endpoints support pagination
- All write operations return 201 (Created) or 200 (Updated)

---

# Authentication & Authorization

## JWT Token Structure
- Token issued on login, valid for 24 hours
- Refresh token valid for 7 days
- Include token in header: `Authorization: Bearer <token>`

## Role-Based Access Control (RBAC)
```
- MUSICIAN: Can create bands, apply to gigs, post recruitment ads
- VENUE_OWNER: Can post gigs, manage applications, record payments
- ADMIN: Full access to all endpoints
```

## Token Endpoints

### POST /auth/register
Register a new user account.

**Request Body:**
```json
{
  "email": "string (email format, unique)",
  "password": "string (min 8 chars)",
  "name": "string",
  "role": "MUSICIAN | VENUE_OWNER",
  "city": "string (optional)",
  "bio": "string (optional)"
}
```

**Response (201):**
```json
{
  "user_id": "integer",
  "email": "string",
  "name": "string",
  "role": "string",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `users` with hashed password
- Validate unique email constraint

---

### POST /auth/login
Authenticate user and return JWT tokens.

**Request Body:**
```json
{
  "email": "string",
  "password": "string"
}
```

**Response (200):**
```json
{
  "access_token": "string (JWT)",
  "refresh_token": "string",
  "expires_in": 86400,
  "user": {
    "user_id": "integer",
    "email": "string",
    "name": "string",
    "role": "string"
  }
}
```

**Database Operations:**
- SELECT user by email
- Verify password hash

---

### POST /auth/refresh
Refresh access token using refresh token.

**Request Header:**
```
Authorization: Bearer <refresh_token>
```

**Response (200):**
```json
{
  "access_token": "string (JWT)",
  "expires_in": 86400
}
```

---

### POST /auth/logout
Invalidate user session (optional; token-based systems often skip this).

**Request:** Empty body  
**Response (200):** `{ "message": "Logged out successfully" }`

---

# API Endpoints

## 1. User Profile Endpoints

### GET /users/{id}
Fetch user profile details.

**Parameters:**
- `id` (path, required): User ID

**Response (200):**
```json
{
  "user_id": "integer",
  "email": "string",
  "name": "string",
  "role": "MUSICIAN | VENUE_OWNER | ADMIN",
  "city": "string",
  "bio": "string",
  "profile_pic": "string (URL)",
  "instruments": ["string (optional, for musicians)"],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- SELECT from `users` where `user_id = {id}`
- JOIN with `user_instruments` if musician

**RBAC:** User can view own profile; admins can view any

---

### PUT /users/{id}
Update user profile.

**Request Body:**
```json
{
  "name": "string (optional)",
  "city": "string (optional)",
  "bio": "string (optional)",
  "profile_pic": "string (optional, URL)",
  "instruments": ["string (optional, array for musicians)"]
}
```

**Response (200):**
```json
{
  "user_id": "integer",
  "updated_at": "ISO8601",
  "message": "Profile updated successfully"
}
```

**Database Operations:**
- UPDATE `users` set fields where `user_id = {id}`
- INSERT/DELETE from `user_instruments` if instruments updated

**RBAC:** User can only update own profile

---

### GET /users/{id}/dashboard
Fetch user dashboard summary (activity, upcoming gigs, stats).

**Parameters:**
- `id` (path, required): User ID

**Response (200):**
```json
{
  "user_id": "integer",
  "user_name": "string",
  "role": "string",
  "stats": {
    "total_gigs_posted": "integer (for venue owners)",
    "total_gigs_played": "integer (for musicians)",
    "total_applications": "integer",
    "average_rating": "float",
    "pending_payments": "float"
  },
  "upcoming_gigs": [
    {
      "gig_id": "integer",
      "title": "string",
      "date": "ISO8601",
      "pay": "float"
    }
  ],
  "pending_applications": [
    {
      "application_id": "integer",
      "gig_title": "string",
      "band_name": "string",
      "status": "SUBMITTED | ACCEPTED | REJECTED"
    }
  ],
  "pending_payments": [
    {
      "payment_id": "integer",
      "booking_id": "integer",
      "amount": "float",
      "status": "PENDING | PAID"
    }
  ]
}
```

**Database Operations:**
- SELECT + aggregates from `users`, `gig_listings`, `applications`, `bookings_contracts`, `payments`
- Use GROUP BY and COUNT/SUM for stats

---

## 2. Band Management Endpoints

### GET /bands
List bands managed/owned by user.

**Query Parameters:**
- `user_id` (required): Filter bands by user
- `page` (optional): Page number
- `limit` (optional): Results per page

**Response (200):**
```json
{
  "total": "integer",
  "page": "integer",
  "limit": "integer",
  "bands": [
    {
      "band_id": "integer",
      "name": "string",
      "description": "string",
      "genres": ["string"],
      "member_count": "integer",
      "created_at": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `bands` where `created_by = {user_id}` (or band member check)
- JOIN with `band_genres`, COUNT `band_members`
- LIMIT and OFFSET for pagination

**RBAC:** Musicians only

---

### POST /bands
Create new band.

**Request Body:**
```json
{
  "name": "string (required, unique per user)",
  "description": "string (optional)",
  "genres": ["string (optional, array)"]
}
```

**Response (201):**
```json
{
  "band_id": "integer",
  "name": "string",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `bands` (name, description, created_by)
- INSERT into `band_genres` for each genre
- Enforce unique constraint on (user_id, band_name)

**RBAC:** Musicians only

---

### GET /bands/{id}
Get band profile with members.

**Parameters:**
- `id` (path, required): Band ID

**Response (200):**
```json
{
  "band_id": "integer",
  "name": "string",
  "description": "string",
  "genres": ["string"],
  "members": [
    {
      "member_id": "integer",
      "user_id": "integer",
      "name": "string",
      "instruments": ["string"],
      "joined_at": "ISO8601"
    }
  ],
  "created_at": "ISO8601",
  "created_by": "integer"
}
```

**Database Operations:**
- SELECT from `bands` where `band_id = {id}`
- JOIN with `band_members` → `users`
- JOIN with `band_genres`
- JOIN with `user_instruments` (per member)

---

### PUT /bands/{id}
Update band information.

**Request Body:**
```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "genres": ["string (optional, replaces existing)"]
}
```

**Response (200):**
```json
{
  "band_id": "integer",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `bands` set fields
- DELETE old `band_genres` rows + INSERT new ones (if genres updated)

**RBAC:** Band creator only

---

### POST /bands/{id}/members
Add member to band.

**Request Body:**
```json
{
  "user_id": "integer",
  "instruments": ["string (optional, array)"]
}
```

**Response (201):**
```json
{
  "member_id": "integer",
  "band_id": "integer",
  "user_id": "integer"
}
```

**Database Operations:**
- INSERT into `band_members` (band_id, user_id)
- INSERT into `user_instruments` for each instrument
- Prevent duplicate membership (unique constraint)

**RBAC:** Band creator only

---

### DELETE /bands/{id}/members/{member_id}
Remove member from band.

**Parameters:**
- `id` (path): Band ID
- `member_id` (path): Band member ID

**Response (200):**
```json
{
  "message": "Member removed"
}
```

**Database Operations:**
- DELETE from `band_members` where `band_id = {id}` AND `user_id = {member_id}`

**RBAC:** Band creator only

---

## 3. Gig Listing Endpoints

### GET /gigs/browse
Browse all open gigs with filters.

**Query Parameters:**
- `city` (optional): Filter by city
- `genre` (optional): Filter by genre
- `date_from`, `date_to` (optional): Date range (ISO8601)
- `pay_min`, `pay_max` (optional): Pay range
- `search` (optional): Text search in title/description
- `status` (optional): Default "OPEN"
- `sort_by` (optional): "date", "pay", "newest"
- `page`, `limit` (optional): Pagination

**Response (200):**
```json
{
  "total": "integer",
  "page": "integer",
  "gigs": [
    {
      "gig_id": "integer",
      "title": "string",
      "venue_name": "string",
      "date": "ISO8601",
      "city": "string",
      "genres": ["string"],
      "pay": "float",
      "status": "OPEN | BOOKED | CANCELLED"
    }
  ]
}
```

**Database Operations:**
- SELECT from `gig_listings` with multiple WHERE conditions
- JOIN with `users` (venue owner info)
- JOIN with `gig_genres` (optional, if genres table exists)
- Use indexes on (city, date, status, pay)
- LIMIT, OFFSET for pagination
- ORDER BY based on sort_by parameter

---

### GET /gigs/{id}
Get full gig details.

**Parameters:**
- `id` (path): Gig ID

**Response (200):**
```json
{
  "gig_id": "integer",
  "title": "string",
  "description": "string",
  "venue_owner": {
    "user_id": "integer",
    "name": "string",
    "contact": "string"
  },
  "date": "ISO8601",
  "end_time": "ISO8601",
  "city": "string",
  "location_details": "string",
  "genres": ["string"],
  "pay_amount": "float",
  "requirements": "string",
  "status": "OPEN | BOOKED | CANCELLED",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- SELECT from `gig_listings` where `gig_id = {id}`
- JOIN with `users` for venue owner
- JOIN with `gig_genres` (if applicable)

---

### POST /gigs
Create new gig listing (venue owner only).

**Request Body:**
```json
{
  "title": "string (required)",
  "description": "string",
  "date": "ISO8601 (required, must be future date)",
  "end_time": "ISO8601 (required)",
  "city": "string (required)",
  "location_details": "string",
  "genres": ["string (optional)"],
  "pay_amount": "float (required, >= 0)",
  "requirements": "string (optional)"
}
```

**Response (201):**
```json
{
  "gig_id": "integer",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `gig_listings`
- Validate date is in future
- Validate pay_amount >= 0
- INSERT into `gig_genres` for each genre
- Set status = 'OPEN'

**RBAC:** Venue owners only

---

### PUT /gigs/{id}
Update gig listing.

**Request Body:**
```json
{
  "title": "string (optional)",
  "description": "string (optional)",
  "date": "ISO8601 (optional)",
  "pay_amount": "float (optional)",
  "genres": ["string (optional)"]
}
```

**Response (200):**
```json
{
  "gig_id": "integer",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `gig_listings` where `gig_id = {id}`
- DELETE old `gig_genres` + INSERT new (if genres updated)

**RBAC:** Venue owner only (creator check)

---

### DELETE /gigs/{id}
Delete/cancel gig listing.

**Parameters:**
- `id` (path): Gig ID

**Response (200):**
```json
{
  "message": "Gig deleted"
}
```

**Database Operations:**
- DELETE from `gig_listings` where `gig_id = {id}`
- Or UPDATE `gig_listings` set `status = 'CANCELLED'` (soft delete recommended)

**RBAC:** Venue owner only (creator check)

---

## 4. Application Endpoints

### POST /applications
Submit application for a gig (musician/band).

**Request Body:**
```json
{
  "gig_id": "integer (required)",
  "band_id": "integer (required, band musician belongs to)"
}
```

**Response (201):**
```json
{
  "application_id": "integer",
  "gig_id": "integer",
  "band_id": "integer",
  "status": "SUBMITTED",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `applications` (gig_id, band_id, status='SUBMITTED')
- Enforce unique constraint on (gig_id, band_id) - one application per band per gig
- Validate band exists and user is member
- Validate gig exists and status = 'OPEN'

**RBAC:** Musicians only

---

### GET /applications/{id}
Get application details.

**Parameters:**
- `id` (path): Application ID

**Response (200):**
```json
{
  "application_id": "integer",
  "gig_id": "integer",
  "gig_title": "string",
  "band_id": "integer",
  "band_name": "string",
  "status": "SUBMITTED | SHORTLISTED | ACCEPTED | REJECTED | WITHDRAWN",
  "applied_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- SELECT from `applications` where `application_id = {id}`
- JOIN with `gig_listings`, `bands`

---

### GET /applications
List applications with filters.

**Query Parameters:**
- `gig_id` (optional): Filter by gig (venue owner)
- `band_id` (optional): Filter by band (musician)
- `status` (optional): SUBMITTED, ACCEPTED, REJECTED, etc.
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "page": "integer",
  "applications": [
    {
      "application_id": "integer",
      "gig_id": "integer",
      "gig_title": "string",
      "band_id": "integer",
      "band_name": "string",
      "status": "string"
    }
  ]
}
```

**Database Operations:**
- SELECT from `applications` with WHERE conditions
- JOIN with `gig_listings`, `bands`
- LIMIT, OFFSET for pagination

---

### PUT /applications/{id}
Update application status (accept/reject/shortlist).

**Request Body:**
```json
{
  "status": "ACCEPTED | REJECTED | SHORTLISTED | WITHDRAWN"
}
```

**Response (200):**
```json
{
  "application_id": "integer",
  "status": "string",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `applications` set `status = {status}` where `application_id = {id}`
- If status = 'ACCEPTED':
  - Trigger: Create booking record
  - Trigger: Block availability dates for band + venue
  - Trigger: Reject/withdraw other applications for same gig

**RBAC:** Venue owner (accept/reject/shortlist), musician (withdraw)

---

### PUT /applications/{id}/withdraw
Withdraw application (musician only).

**Parameters:**
- `id` (path): Application ID

**Response (200):**
```json
{
  "message": "Application withdrawn"
}
```

**Database Operations:**
- UPDATE `applications` set `status = 'WITHDRAWN'` where `application_id = {id}`

**RBAC:** Application submitter only

---

## 5. Booking & Contract Endpoints

### GET /bookings
List bookings for user.

**Query Parameters:**
- `user_id` (required)
- `status` (optional): PENDING, SIGNED, COMPLETED
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "page": "integer",
  "bookings": [
    {
      "booking_id": "integer",
      "gig_id": "integer",
      "gig_title": "string",
      "band_id": "integer",
      "band_name": "string",
      "date": "ISO8601",
      "pay_total": "float",
      "status": "PENDING | SIGNED | COMPLETED"
    }
  ]
}
```

**Database Operations:**
- SELECT from `bookings_contracts` where user is band member OR venue owner
- JOIN with `gig_listings`, `bands`
- LIMIT, OFFSET

---

### GET /bookings/{id}
Get booking/contract details.

**Parameters:**
- `id` (path): Booking ID

**Response (200):**
```json
{
  "booking_id": "integer",
  "gig_id": "integer",
  "gig_details": {
    "title": "string",
    "date": "ISO8601",
    "location": "string"
  },
  "band_id": "integer",
  "band_name": "string",
  "venue_owner_id": "integer",
  "venue_owner_name": "string",
  "pay_total": "float",
  "deposit_amount": "float",
  "final_payment": "float",
  "status": "PENDING | SIGNED | COMPLETED",
  "band_signed_at": "ISO8601 (optional)",
  "venue_signed_at": "ISO8601 (optional)",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- SELECT from `bookings_contracts` where `booking_id = {id}`
- JOIN with `gig_listings`, `bands`, `users`
- JOIN with `payments` to fetch deposit/final payment

---

### PUT /bookings/{id}/sign
Sign booking (e-signature by band or venue owner).

**Request Body:**
```json
{
  "signed_by_role": "MUSICIAN | VENUE_OWNER"
}
```

**Response (200):**
```json
{
  "booking_id": "integer",
  "signed_at": "ISO8601",
  "status": "SIGNED (if both parties signed)"
}
```

**Database Operations:**
- UPDATE `bookings_contracts`:
  - If role = MUSICIAN: set `band_signed_at = NOW()`
  - If role = VENUE_OWNER: set `venue_signed_at = NOW()`
  - If both signed: set `status = 'SIGNED'`

**RBAC:** Band member or venue owner

---

## 6. Availability/Calendar Endpoints

### GET /availability/{user_id}
Get user's availability calendar (booked + blocked dates).

**Parameters:**
- `user_id` (path): User ID

**Query Parameters:**
- `month` (optional): YYYY-MM format
- `date_from`, `date_to` (optional): Date range

**Response (200):**
```json
{
  "user_id": "integer",
  "busy_dates": [
    {
      "date": "ISO8601",
      "reason": "GIG | BLOCKED | PERSONAL"
    }
  ],
  "booked_gigs": [
    {
      "gig_id": "integer",
      "date": "ISO8601",
      "title": "string"
    }
  ]
}
```

**Database Operations:**
- SELECT from `availability_calendar` where `user_id = {user_id}`
- SELECT from `bookings_contracts` → `gig_listings` for booked gigs

---

### POST /availability
Block date as unavailable.

**Request Body:**
```json
{
  "user_id": "integer (required)",
  "date": "ISO8601 (required)",
  "reason": "BLOCKED | PERSONAL | OTHER",
  "notes": "string (optional)"
}
```

**Response (201):**
```json
{
  "availability_id": "integer",
  "date": "ISO8601",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `availability_calendar` (user_id, date, reason, notes)
- Check for conflicts with existing bookings (optional warning)

**RBAC:** User can block own dates only

---

### DELETE /availability/{id}
Remove blocked date.

**Parameters:**
- `id` (path): Availability record ID

**Response (200):**
```json
{
  "message": "Date unblocked"
}
```

**Database Operations:**
- DELETE from `availability_calendar` where `availability_id = {id}`

**RBAC:** User can unblock own dates only

---

## 7. Setlist Endpoints

### GET /bands/{band_id}/setlists
List setlists for a band.

**Parameters:**
- `band_id` (path): Band ID

**Query Parameters:**
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "page": "integer",
  "setlists": [
    {
      "setlist_id": "integer",
      "name": "string",
      "gig_id": "integer (optional)",
      "song_count": "integer",
      "created_at": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `setlists` where `band_id = {band_id}`
- COUNT songs per setlist from `setlist_songs`

---

### POST /setlists
Create new setlist.

**Request Body:**
```json
{
  "band_id": "integer (required)",
  "name": "string (required)",
  "gig_id": "integer (optional, if for specific gig)"
}
```

**Response (201):**
```json
{
  "setlist_id": "integer",
  "name": "string",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `setlists` (band_id, name, gig_id)

**RBAC:** Band members only

---

### GET /setlists/{id}
Get setlist with all songs.

**Parameters:**
- `id` (path): Setlist ID

**Response (200):**
```json
{
  "setlist_id": "integer",
  "name": "string",
  "band_id": "integer",
  "gig_id": "integer (optional)",
  "songs": [
    {
      "song_id": "integer",
      "title": "string",
      "artist": "string",
      "duration_minutes": "float",
      "order": "integer"
    }
  ],
  "total_duration": "float"
}
```

**Database Operations:**
- SELECT from `setlists` where `setlist_id = {id}`
- SELECT from `setlist_songs` where `setlist_id = {id}` ORDER BY `order`
- SUM duration for total

---

### PUT /setlists/{id}
Update setlist (name, gig assignment).

**Request Body:**
```json
{
  "name": "string (optional)",
  "gig_id": "integer (optional)"
}
```

**Response (200):**
```json
{
  "setlist_id": "integer",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `setlists` set fields where `setlist_id = {id}`

**RBAC:** Band members only

---

### DELETE /setlists/{id}
Delete setlist.

**Parameters:**
- `id` (path): Setlist ID

**Response (200):**
```json
{
  "message": "Setlist deleted"
}
```

**Database Operations:**
- DELETE from `setlist_songs` where `setlist_id = {id}` (cascade)
- DELETE from `setlists` where `setlist_id = {id}`

**RBAC:** Band members only

---

### POST /setlists/{id}/songs
Add song to setlist.

**Request Body:**
```json
{
  "title": "string (required)",
  "artist": "string (optional)",
  "duration_minutes": "float (required)"
}
```

**Response (201):**
```json
{
  "song_id": "integer",
  "setlist_id": "integer",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `setlist_songs` (setlist_id, title, artist, duration_minutes)
- Set order = max(current orders) + 1

**RBAC:** Band members only

---

### PUT /setlists/{id}/songs/{song_id}
Update song in setlist (reorder, edit details).

**Request Body:**
```json
{
  "title": "string (optional)",
  "artist": "string (optional)",
  "duration_minutes": "float (optional)",
  "order": "integer (optional, for reordering)"
}
```

**Response (200):**
```json
{
  "song_id": "integer",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `setlist_songs` set fields where `song_id = {song_id}`

**RBAC:** Band members only

---

### DELETE /setlists/{id}/songs/{song_id}
Remove song from setlist.

**Parameters:**
- `id` (path): Setlist ID
- `song_id` (path): Song ID

**Response (200):**
```json
{
  "message": "Song removed"
}
```

**Database Operations:**
- DELETE from `setlist_songs` where `song_id = {song_id}`

**RBAC:** Band members only

---

## 8. Payment Endpoints

### GET /payments
List payments for user with filters.

**Query Parameters:**
- `user_id` (required)
- `status` (optional): PENDING, PAID, LATE
- `date_from`, `date_to` (optional)
- `booking_id` (optional)
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "page": "integer",
  "payments": [
    {
      "payment_id": "integer",
      "booking_id": "integer",
      "gig_title": "string",
      "amount": "float",
      "payment_type": "DEPOSIT | FINAL",
      "status": "PENDING | PAID",
      "due_date": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `payments` with WHERE conditions
- JOIN with `bookings_contracts`, `gig_listings`
- LIMIT, OFFSET

---

### GET /payments/{id}
Get payment details.

**Parameters:**
- `id` (path): Payment ID

**Response (200):**
```json
{
  "payment_id": "integer",
  "booking_id": "integer",
  "gig_id": "integer",
  "gig_title": "string",
  "band_id": "integer",
  "band_name": "string",
  "amount": "float",
  "payment_type": "DEPOSIT | FINAL",
  "status": "PENDING | PAID",
  "due_date": "ISO8601",
  "paid_date": "ISO8601 (optional)",
  "notes": "string (optional)"
}
```

**Database Operations:**
- SELECT from `payments` where `payment_id = {id}`
- JOIN with `bookings_contracts`, `gig_listings`, `bands`

---

### POST /payments
Record new payment.

**Request Body:**
```json
{
  "booking_id": "integer (required)",
  "amount": "float (required, > 0)",
  "payment_type": "DEPOSIT | FINAL",
  "paid_date": "ISO8601 (required)"
}
```

**Response (201):**
```json
{
  "payment_id": "integer",
  "booking_id": "integer",
  "status": "PAID",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `payments` (booking_id, amount, payment_type, paid_date, status='PAID')
- Validate amount > 0
- If payment_type='DEPOSIT': ensure amount <= booking.pay_total
- Trigger: Update booking/payment status

**RBAC:** Venue owner only

---

### PUT /payments/{id}
Update payment status.

**Request Body:**
```json
{
  "status": "PAID | PENDING",
  "notes": "string (optional)"
}
```

**Response (200):**
```json
{
  "payment_id": "integer",
  "status": "string",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `payments` set `status = {status}`, `notes = {notes}` where `payment_id = {id}`

**RBAC:** Venue owner only

---

## 9. Recruitment Ads Endpoints

### GET /recruitment-ads/browse
Browse recruitment ads with filters.

**Query Parameters:**
- `instrument` (optional)
- `genre` (optional)
- `city` (optional)
- `search` (optional)
- `sort_by` (optional): "newest", "oldest"
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "page": "integer",
  "ads": [
    {
      "ad_id": "integer",
      "title": "string",
      "posted_by": "string",
      "instruments_needed": ["string"],
      "genres": ["string"],
      "city": "string",
      "posted_at": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `recruitment_ads` with WHERE conditions
- JOIN with instruments/genres (if separate tables)
- ORDER BY posted_at (or other sort_by)
- LIMIT, OFFSET

---

### GET /recruitment-ads/{id}
Get recruitment ad details.

**Parameters:**
- `id` (path): Ad ID

**Response (200):**
```json
{
  "ad_id": "integer",
  "title": "string",
  "description": "string",
  "posted_by": {
    "user_id": "integer",
    "name": "string",
    "instruments": ["string"]
  },
  "instruments_needed": ["string"],
  "genres": ["string"],
  "city": "string",
  "posted_at": "ISO8601"
}
```

**Database Operations:**
- SELECT from `recruitment_ads` where `ad_id = {id}`
- JOIN with `users`

---

### POST /recruitment-ads
Create new recruitment ad.

**Request Body:**
```json
{
  "title": "string (required)",
  "description": "string (optional)",
  "instruments_needed": ["string (required)"],
  "genres": ["string (optional)"],
  "city": "string (required)"
}
```

**Response (201):**
```json
{
  "ad_id": "integer",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `recruitment_ads` (title, description, posted_by, city)
- INSERT into ad_instruments (if separate table)

**RBAC:** Musicians only

---

### PUT /recruitment-ads/{id}
Update recruitment ad.

**Request Body:**
```json
{
  "title": "string (optional)",
  "description": "string (optional)",
  "instruments_needed": ["string (optional)"],
  "status": "ACTIVE | CLOSED"
}
```

**Response (200):**
```json
{
  "ad_id": "integer",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `recruitment_ads` set fields where `ad_id = {id}`

**RBAC:** Ad creator only

---

### DELETE /recruitment-ads/{id}
Delete recruitment ad.

**Parameters:**
- `id` (path): Ad ID

**Response (200):**
```json
{
  "message": "Ad deleted"
}
```

**Database Operations:**
- DELETE from `recruitment_ads` where `ad_id = {id}`

**RBAC:** Ad creator only

---

## 10. Reviews & Disputes Endpoints

### POST /reviews
Submit review after a booking.

**Request Body:**
```json
{
  "booking_id": "integer (required)",
  "rating": "integer (required, 1-5)",
  "comment": "string (optional)"
}
```

**Response (201):**
```json
{
  "review_id": "integer",
  "booking_id": "integer",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `reviews_disputes` (booking_id, reviewer_id, rating, comment, type='REVIEW')
- Validate booking is completed/closed
- Validate no duplicate review per booking/user pair

**RBAC:** Parties in the booking only

---

### GET /reviews/{id}
Get review details.

**Parameters:**
- `id` (path): Review ID

**Response (200):**
```json
{
  "review_id": "integer",
  "booking_id": "integer",
  "reviewer": {
    "user_id": "integer",
    "name": "string"
  },
  "rating": "integer",
  "comment": "string",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- SELECT from `reviews_disputes` where `review_id = {id}` AND `type = 'REVIEW'`

---

### GET /reviews
List reviews for user.

**Query Parameters:**
- `user_id` (required): User receiving reviews
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "page": "integer",
  "reviews": [
    {
      "review_id": "integer",
      "reviewer_name": "string",
      "rating": "integer",
      "comment": "string",
      "created_at": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `reviews_disputes` where type='REVIEW' and reviewer_id={user_id} or reviewee_id={user_id}
- LIMIT, OFFSET

---

### POST /disputes
File new dispute/flag.

**Request Body:**
```json
{
  "booking_id": "integer (required)",
  "reason": "NO_SHOW | PAYMENT_ISSUE | QUALITY_ISSUE | OTHER",
  "description": "string (required)",
  "evidence_urls": ["string (optional, array of URLs)"]
}
```

**Response (201):**
```json
{
  "dispute_id": "integer",
  "booking_id": "integer",
  "status": "OPEN",
  "created_at": "ISO8601"
}
```

**Database Operations:**
- INSERT into `reviews_disputes` (booking_id, filed_by, reason, description, type='DISPUTE', status='OPEN')

**RBAC:** Booking parties only

---

### GET /disputes/{id}
Get dispute details.

**Parameters:**
- `id` (path): Dispute ID

**Response (200):**
```json
{
  "dispute_id": "integer",
  "booking_id": "integer",
  "filed_by": {
    "user_id": "integer",
    "name": "string"
  },
  "reason": "string",
  "description": "string",
  "status": "OPEN | RESOLVED | DISMISSED",
  "resolution": "string (optional)",
  "created_at": "ISO8601",
  "resolved_at": "ISO8601 (optional)"
}
```

**Database Operations:**
- SELECT from `reviews_disputes` where `dispute_id = {id}` AND `type = 'DISPUTE'`

---

### GET /disputes
List disputes for user.

**Query Parameters:**
- `user_id` (required)
- `status` (optional): OPEN, RESOLVED, DISMISSED
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "disputes": [
    {
      "dispute_id": "integer",
      "booking_id": "integer",
      "reason": "string",
      "status": "string",
      "created_at": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `reviews_disputes` where type='DISPUTE' and (filed_by={user_id} or involved party)

---

### PUT /disputes/{id}
Resolve dispute (admin only).

**Request Body:**
```json
{
  "status": "RESOLVED | DISMISSED",
  "resolution": "string (optional)"
}
```

**Response (200):**
```json
{
  "dispute_id": "integer",
  "status": "string",
  "resolved_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `reviews_disputes` set `status = {status}`, `resolution = {resolution}`, `resolved_at = NOW()` where `dispute_id = {id}`

**RBAC:** Admin only

---

## 11. Admin Endpoints

### GET /admin/dashboard
Get admin dashboard statistics.

**Response (200):**
```json
{
  "stats": {
    "total_users": "integer",
    "total_musicians": "integer",
    "total_venue_owners": "integer",
    "active_gigs": "integer",
    "total_bookings": "integer",
    "platform_revenue": "float",
    "pending_disputes": "integer"
  },
  "recent_activity": {
    "new_users_today": "integer",
    "new_gigs_today": "integer",
    "new_bookings_today": "integer"
  }
}
```

**Database Operations:**
- SELECT COUNT(*) from `users` (with role filter)
- SELECT COUNT(*) from `gig_listings` where status='OPEN'
- SELECT COUNT(*) from `bookings_contracts`
- SELECT SUM(amount) from `payments` where status='PAID'
- SELECT COUNT(*) from `reviews_disputes` where type='DISPUTE' and status='OPEN'

**RBAC:** Admin only

---

### GET /admin/users
List all users (admin view).

**Query Parameters:**
- `role` (optional): MUSICIAN, VENUE_OWNER
- `status` (optional): ACTIVE, BANNED
- `search` (optional): Search by email/name
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "users": [
    {
      "user_id": "integer",
      "email": "string",
      "name": "string",
      "role": "string",
      "status": "ACTIVE | BANNED",
      "created_at": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `users` with filters
- LIMIT, OFFSET

**RBAC:** Admin only

---

### PUT /admin/users/{id}
Update user (ban/unban, role change).

**Request Body:**
```json
{
  "status": "ACTIVE | BANNED",
  "role": "MUSICIAN | VENUE_OWNER | ADMIN"
}
```

**Response (200):**
```json
{
  "user_id": "integer",
  "status": "string",
  "updated_at": "ISO8601"
}
```

**Database Operations:**
- UPDATE `users` set `status = {status}`, `role = {role}` where `user_id = {id}`

**RBAC:** Admin only

---

### POST /admin/users/{id}/reset-password
Reset user password.

**Request Body:**
```json
{
  "new_password": "string (min 8 chars)"
}
```

**Response (200):**
```json
{
  "message": "Password reset successfully"
}
```

**Database Operations:**
- UPDATE `users` set `password_hash = hash({new_password})` where `user_id = {id}`

**RBAC:** Admin only

---

### GET /admin/gigs
List all gigs (admin view).

**Query Parameters:**
- `status` (optional)
- `city` (optional)
- `search` (optional)
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "gigs": [
    {
      "gig_id": "integer",
      "title": "string",
      "venue_owner": "string",
      "status": "string",
      "date": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `gig_listings` with filters
- LIMIT, OFFSET

**RBAC:** Admin only

---

### DELETE /admin/gigs/{id}
Delete gig (admin moderation).

**Parameters:**
- `id` (path): Gig ID

**Response (200):**
```json
{
  "message": "Gig deleted"
}
```

**Database Operations:**
- DELETE from `gig_listings` where `gig_id = {id}`

**RBAC:** Admin only

---

### GET /admin/disputes
List all disputes (admin view).

**Query Parameters:**
- `status` (optional): OPEN, RESOLVED, DISMISSED
- `page`, `limit` (optional)

**Response (200):**
```json
{
  "total": "integer",
  "disputes": [
    {
      "dispute_id": "integer",
      "booking_id": "integer",
      "filed_by": "string",
      "reason": "string",
      "status": "string",
      "created_at": "ISO8601"
    }
  ]
}
```

**Database Operations:**
- SELECT from `reviews_disputes` where type='DISPUTE'
- LIMIT, OFFSET

**RBAC:** Admin only

---

### PUT /admin/disputes/{id}
Resolve dispute (admin).

**Request Body:**
```json
{
  "status": "RESOLVED | DISMISSED",
  "resolution": "string"
}
```

**Response (200):**
```json
{
  "dispute_id": "integer",
  "status": "string"
}
```

**Database Operations:**
- UPDATE `reviews_disputes` set `status`, `resolution`, `resolved_at` where `dispute_id = {id}`

**RBAC:** Admin only

---

# Error Handling

All endpoints return errors in this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": "Additional details (optional)"
  }
}
```

## Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_CREDENTIALS` | 401 | Email or password incorrect |
| `UNAUTHORIZED` | 401 | Missing or invalid token |
| `FORBIDDEN` | 403 | User lacks permission |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Duplicate entry / constraint violation |
| `VALIDATION_ERROR` | 400 | Invalid input parameters |
| `INTERNAL_ERROR` | 500 | Server error |

---

# Rate Limiting

Rate limiting applies per IP/user:

| Role | Requests/Hour |
|------|---|
| Unauthenticated | 60 |
| Musician | 1000 |
| Venue Owner | 2000 |
| Admin | Unlimited |

**Response Header:** `X-RateLimit-Remaining: <count>`

---

# Indexing & Performance

Create these indexes for query performance:

```sql
-- Gigs
CREATE INDEX idx_gig_listings_status ON gig_listings(status);
CREATE INDEX idx_gig_listings_city_date ON gig_listings(city, event_date);
CREATE INDEX idx_gig_listings_created_by ON gig_listings(created_by);

-- Applications
CREATE INDEX idx_applications_gig_id ON applications(gig_id);
CREATE INDEX idx_applications_band_id ON applications(band_id);
CREATE INDEX idx_applications_status ON applications(status);

-- Payments
CREATE INDEX idx_payments_booking_id ON payments(booking_id);
CREATE INDEX idx_payments_status ON payments(payment_status);

-- Bookings
CREATE INDEX idx_bookings_contracts_gig_id ON bookings_contracts(gig_id);
CREATE INDEX idx_bookings_contracts_band_id ON bookings_contracts(band_id);

-- Users
CREATE UNIQUE INDEX idx_users_email ON users(email);

-- Availability
CREATE INDEX idx_availability_calendar_user_date ON availability_calendar(user_id, date);

-- Recruitment Ads
CREATE INDEX idx_recruitment_ads_created_by ON recruitment_ads(created_by);
CREATE INDEX idx_recruitment_ads_city ON recruitment_ads(city);
```

---

# Deployment & Testing

## Pre-deployment Checklist

- [ ] All endpoints tested with valid/invalid inputs
- [ ] RBAC checks enforced on all protected endpoints
- [ ] Rate limiting configured and tested
- [ ] Indexes created and performance verified
- [ ] Error handling standardized
- [ ] JWT token generation/validation working
- [ ] Database transactions working (booking creation, etc.)
- [ ] Triggers executing correctly (status updates, availability blocking)
- [ ] Logging configured
- [ ] API documentation generated (Swagger/OpenAPI optional)

## Testing Endpoints

Use Postman/Insomnia/cURL for manual testing:

```bash
# Example: Register
curl -X POST http://localhost:5000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123","name":"John","role":"MUSICIAN"}'

# Example: Login
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'

# Example: Create gig (with token)
curl -X POST http://localhost:5000/api/v1/gigs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Wedding Band","date":"2026-06-15T18:00:00Z","city":"Karachi","pay_amount":5000}'
```

---

# End of PRD

This document provides complete API specifications for GigVault backend implementation. Use this as the primary reference for coding agents.

