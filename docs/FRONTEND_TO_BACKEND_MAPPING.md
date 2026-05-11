# GigVault — Frontend Pages to Backend API Mapping

This document maps each of the 11 shortlisted frontend pages to their corresponding backend API endpoints.

---

## 1. Register/Login/Profile Page

### Frontend Features
- User registration (email, password, role selection)
- User login with credentials
- View and edit user profile
- Update profile information

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/register` | POST | Register new user (Musician, Venue Owner) |
| `/auth/login` | POST | Authenticate user and return JWT token |
| `/users/{id}` | GET | Fetch user profile details |
| `/users/{id}` | PUT | Update user profile information |
| `/auth/refresh` | POST | Refresh JWT token |
| `/auth/logout` | POST | Logout user (invalidate session) |

### Database Tables Involved
- `users` (primary)

---

## 2. My Dashboard Page

### Frontend Features
- View upcoming gigs (as musician or venue owner)
- Show recent applications status
- Display recent reviews
- Show payment status
- Display notifications/alerts

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/users/{id}/dashboard` | GET | Fetch dashboard summary (activity, stats) |
| `/gigs?user_id={id}&status=upcoming` | GET | Get upcoming gigs for user |
| `/applications?band_id={id}&status=pending` | GET | Get pending applications for bands |
| `/bookings?user_id={id}&status=active` | GET | Get active bookings for user |
| `/reviews?user_id={id}` | GET | Get recent reviews received |
| `/payments?user_id={id}&status=pending` | GET | Get pending payments |
| `/notifications?user_id={id}` | GET | Get user notifications |

### Database Tables Involved
- `users`, `bands`, `gig_listings`, `applications`, `bookings_contracts`, `payments`, `reviews_disputes`

---

## 3. Bands List/Profile (+members) Page

### Frontend Features
- List all bands managed/owned by user
- View band details (name, description, genres)
- View band members and their instruments
- Add new band members
- Remove band members
- Edit band information
- Create new band

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/bands?user_id={id}` | GET | List bands managed by user |
| `/bands/{id}` | GET | Get band details with full profile |
| `/bands` | POST | Create new band |
| `/bands/{id}` | PUT | Update band information |
| `/bands/{id}/members` | GET | Get all members in a band |
| `/bands/{id}/members` | POST | Add member to band |
| `/bands/{id}/members/{member_id}` | DELETE | Remove member from band |

### Database Tables Involved
- `bands`, `band_members`, `users`

---

## 4. Browse Gigs/Search Gigs Page

### Frontend Features
- Display list of all open gigs
- Filter gigs by date range
- Filter gigs by genre
- Filter gigs by city/location
- Filter gigs by pay range
- Search gigs by text/keywords
- Sort results (date, pay, newest)

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/gigs/browse` | GET | Browse all open gigs with filters (date, genre, city, pay, search) |
| `/gigs/{id}` | GET | Get full gig details |

### Query Parameters for `/gigs/browse`
- `city` (optional)
- `genre` (optional)
- `date_from`, `date_to` (optional)
- `pay_min`, `pay_max` (optional)
- `search` (optional)
- `status` (optional, default: open)
- `sort_by` (optional: date, pay, newest)
- `page`, `limit` (pagination)

### Database Tables Involved
- `gig_listings`, `users`, `bands`

---

## 5. Gig Details/Apply/Applications Page

### Frontend Features
- View full gig details
- Apply to gig (as musician/band)
- List all applications received (venue owner)
- Accept/reject/shortlist applications
- View application status (musician)
- Withdraw application

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/gigs/{id}` | GET | Get full gig details |
| `/gigs/{id}/applications` | GET | Get all applications for a gig (venue owner) |
| `/applications` | POST | Submit application for a gig (musician/band) |
| `/applications/{id}` | GET | Get application details |
| `/applications/{id}` | PUT | Update application status (accept/reject/shortlist) |
| `/applications/{id}/withdraw` | PUT | Withdraw application (musician) |

### Database Tables Involved
- `gig_listings`, `applications`, `bands`, `users`

---

## 6. Booking & Calendar/Availability Page

### Frontend Features
- View finalized bookings/contracts
- View visual calendar with booked dates
- Block/mark dates as unavailable
- Unblock/remove blocked dates
- View availability conflicts

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/bookings` | GET | List all bookings for user |
| `/bookings/{id}` | GET | Get booking/contract details |
| `/bookings/{id}/sign` | PUT | Sign booking (musician or venue owner) |
| `/availability/{user_id}` | GET | Get user's availability calendar (busy/blocked dates) |
| `/availability` | POST | Block/mark date as unavailable |
| `/availability/{id}` | DELETE | Unblock/remove blocked date |

### Database Tables Involved
- `bookings_contracts`, `availability_calendar`, `gig_listings`, `applications`, `payments`

---

## 7. Setlists & Songs Page

### Frontend Features
- List setlists for a band
- View setlist details (all songs in setlist)
- Create new setlist
- Add songs to setlist
- Edit song in setlist (reorder, modify details)
- Remove song from setlist
- Delete entire setlist

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/bands/{band_id}/setlists` | GET | List all setlists for a band |
| `/setlists/{id}` | GET | Get setlist details with all songs |
| `/setlists` | POST | Create new setlist |
| `/setlists/{id}` | PUT | Update setlist (name, description) |
| `/setlists/{id}` | DELETE | Delete entire setlist |
| `/setlists/{id}/songs` | GET | Get all songs in setlist |
| `/setlists/{id}/songs` | POST | Add song to setlist |
| `/setlists/{id}/songs/{song_id}` | PUT | Update song in setlist (reorder, modify) |
| `/setlists/{id}/songs/{song_id}` | DELETE | Remove song from setlist |

### Database Tables Involved
- `setlists`, `setlist_songs`, `bands`

---

## 8. Payments Overview Page

### Frontend Features
- List all payments (deposits, final payouts)
- Filter payments by status (pending, paid, late)
- View payment details
- Record new payment (venue owner)
- Update payment status
- View payment history

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/payments` | GET | List all payments for user with filters (status, date range) |
| `/payments/{id}` | GET | Get payment details |
| `/payments` | POST | Record new payment (venue owner) |
| `/payments/{id}` | PUT | Update payment status |
| `/payments?booking_id={id}` | GET | Get payments for specific booking |

### Query Parameters for `/payments`
- `user_id` (required)
- `status` (optional: pending, paid, late)
- `date_from`, `date_to` (optional)
- `page`, `limit` (pagination)

### Database Tables Involved
- `payments`, `bookings_contracts`, `gig_listings`

---

## 9. Recruitment Ads + Filtering Page

### Frontend Features
- Browse all recruitment ads
- Filter ads by instrument
- Filter ads by genre
- Filter ads by location/city
- Search ads by text
- Create new recruitment ad
- Edit own recruitment ad
- Delete own recruitment ad
- View recruitment ad details

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/recruitment-ads/browse` | GET | Browse all recruitment ads with filters (instrument, genre, city, search) |
| `/recruitment-ads/{id}` | GET | Get recruitment ad details |
| `/recruitment-ads` | POST | Create new recruitment ad |
| `/recruitment-ads/{id}` | PUT | Update recruitment ad |
| `/recruitment-ads/{id}` | DELETE | Delete recruitment ad |

### Query Parameters for `/recruitment-ads/browse`
- `instrument` (optional)
- `genre` (optional)
- `city` (optional)
- `search` (optional)
- `sort_by` (optional: newest, oldest)
- `page`, `limit` (pagination)

### Database Tables Involved
- `recruitment_ads`, `users`, `bands`

---

## 10. Reviews & Disputes (leave, moderate) Page

### Frontend Features
- Submit review after a booking (musician or venue owner)
- Rate performance (1-5 stars)
- Write review text
- View all reviews received
- View all reviews given
- File dispute/flag no-show
- Add evidence/comments to dispute
- Admin: View pending disputes
- Admin: Resolve disputes (mark resolved, take action)
- Admin: Approve/reject reviews

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/reviews` | POST | Submit new review for a booking |
| `/reviews/{id}` | GET | Get review details |
| `/reviews?user_id={id}` | GET | Get all reviews for a user (received) |
| `/reviews?author_id={id}` | GET | Get all reviews by a user (given) |
| `/disputes` | POST | File new dispute/flag |
| `/disputes/{id}` | GET | Get dispute details |
| `/disputes?user_id={id}` | GET | Get disputes for user |
| `/admin/disputes` | GET | Get all disputes (admin only) |
| `/admin/disputes/{id}` | PUT | Resolve dispute (admin only) |
| `/admin/reviews` | GET | Get all reviews for moderation (admin only) |
| `/admin/reviews/{id}` | PUT | Approve/reject review (admin only) |

### Database Tables Involved
- `reviews_disputes`, `bookings_contracts`, `users`, `bands`

---

## 11. Admin Dashboard Page

### Frontend Features
- View platform statistics (total users, gigs, active bookings, revenue)
- View all users (with filters)
- Ban/unban users
- Reset user credentials
- View all gig listings
- Delete inappropriate gigs
- View pending disputes and reviews
- Resolve disputes

### Backend Endpoints Required
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/dashboard` | GET | Get admin dashboard statistics |
| `/admin/users` | GET | List all users with filters (role, status, search) |
| `/admin/users/{id}` | PUT | Update user (ban/unban, change role) |
| `/admin/users/{id}/reset-password` | POST | Reset user password |
| `/admin/gigs` | GET | List all gigs with filters |
| `/admin/gigs/{id}` | DELETE | Delete gig listing |
| `/admin/disputes` | GET | List all pending disputes |
| `/admin/disputes/{id}` | PUT | Resolve dispute |
| `/admin/reviews` | GET | List all reviews for moderation |
| `/admin/reviews/{id}` | PUT | Approve/reject review |

### Database Tables Involved
- `users`, `gig_listings`, `applications`, `bookings_contracts`, `reviews_disputes`, `payments`

---

## Summary: Total Endpoints by Category

| Category | Count |
|----------|-------|
| Authentication | 4 |
| User Profile | 3 |
| Bands | 7 |
| Gigs | 5 |
| Applications | 5 |
| Bookings | 5 |
| Availability | 3 |
| Setlists | 9 |
| Payments | 5 |
| Recruitment Ads | 5 |
| Reviews & Disputes | 11 |
| Admin | 10 |
| **Total** | **72** |

---

## Key Notes

1. **Authentication**: All endpoints (except `/auth/register` and `/auth/login`) require a valid JWT token in Authorization header.
2. **Role-Based Access Control (RBAC)**: Certain endpoints are restricted by user role (e.g., venue owner only, admin only).
3. **Pagination**: All list endpoints (`GET`) should support `page` and `limit` query parameters.
4. **Filtering & Search**: Browse endpoints support multiple filters as listed in their respective sections.
5. **Error Handling**: All endpoints should return appropriate HTTP status codes (200, 201, 400, 401, 403, 404, 500) with error messages.

---
