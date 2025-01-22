from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from flask_migrate import Migrate

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel_booking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add after creating the db object
migrate = Migrate(app, db)

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    bookings = db.relationship('Booking', backref='user', lazy=True)
    is_admin = db.Column(db.Boolean, default=False)

class Hotel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(200))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    rooms = db.relationship('Room', backref='hotel', lazy=True)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    available = db.Column(db.Boolean, default=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='confirmed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Add these relationships
    hotel = db.relationship('Hotel', backref='bookings')
    room = db.relationship('Room', backref='bookings')

class Currency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(3), unique=True, nullable=False)
    symbol = db.Column(db.String(5), nullable=False)
    rate_to_gbp = db.Column(db.Float, nullable=False)  # Exchange rate relative to GBP
    is_active = db.Column(db.Boolean, default=True)

class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    peak_rate = db.Column(db.Float, nullable=False)
    off_peak_rate = db.Column(db.Float, nullable=False)

# Add this after your model definitions but before the routes

CITY_DATA = {
    'Aberdeen': {'capacity': 90, 'peak_rate': 140, 'off_peak_rate': 70},
    'Belfast': {'capacity': 80, 'peak_rate': 130, 'off_peak_rate': 70},
    'Birmingham': {'capacity': 110, 'peak_rate': 150, 'off_peak_rate': 75},
    'Bristol': {'capacity': 100, 'peak_rate': 140, 'off_peak_rate': 70},
    'Cardiff': {'capacity': 90, 'peak_rate': 130, 'off_peak_rate': 70},
    'Edinburgh': {'capacity': 120, 'peak_rate': 160, 'off_peak_rate': 80},
    'Glasgow': {'capacity': 140, 'peak_rate': 150, 'off_peak_rate': 75},
    'London': {'capacity': 160, 'peak_rate': 200, 'off_peak_rate': 100},
    'Manchester': {'capacity': 150, 'peak_rate': 180, 'off_peak_rate': 90},
    'New Castle': {'capacity': 90, 'peak_rate': 120, 'off_peak_rate': 70},
    'Norwich': {'capacity': 90, 'peak_rate': 130, 'off_peak_rate': 70},
    'Nottingham': {'capacity': 110, 'peak_rate': 130, 'off_peak_rate': 70},
    'Oxford': {'capacity': 90, 'peak_rate': 180, 'off_peak_rate': 90},
    'Plymouth': {'capacity': 80, 'peak_rate': 180, 'off_peak_rate': 90},
    'Swansea': {'capacity': 70, 'peak_rate': 130, 'off_peak_rate': 70},
    'Bournemouth': {'capacity': 90, 'peak_rate': 130, 'off_peak_rate': 70},
    'Kent': {'capacity': 100, 'peak_rate': 140, 'off_peak_rate': 80}
}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    # Get search parameters
    city = request.args.get('city')
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')
    rooms = request.args.get('rooms', type=int)
    room_type = request.args.get('room_type')

    # Base query
    hotels_query = Hotel.query

    # Apply filters
    if city:
        hotels_query = hotels_query.filter(Hotel.city == city)

    # Get all hotels that match the city filter
    hotels = hotels_query.all()

    # Further filter hotels based on room criteria
    if any([rooms, room_type]):
        filtered_hotels = []
        for hotel in hotels:
            available_rooms = []
            for room in hotel.rooms:
                # Check if room matches type criteria
                type_match = True
                if room_type and room_type != 'any':
                    type_match = room_type.lower() in room.type.lower()

                # Check if room matches capacity criteria
                capacity_match = True
                if rooms:
                    capacity_match = room.capacity >= rooms

                # Check if room is available for the selected dates
                date_match = True
                if check_in and check_out:
                    try:
                        check_in_date = datetime.strptime(check_in, '%Y-%m-%d')
                        check_out_date = datetime.strptime(check_out, '%Y-%m-%d')

                        # Check if room is not booked for these dates
                        existing_booking = Booking.query.filter(
                            Booking.room_id == room.id,
                            Booking.status == 'confirmed',
                            ~(
                                (Booking.check_out <= check_in_date) |
                                (Booking.check_in >= check_out_date)
                            )
                        ).first()

                        date_match = not existing_booking
                    except ValueError:
                        date_match = True

                if type_match and capacity_match and date_match:
                    available_rooms.append(room)

            if available_rooms:
                setattr(hotel, 'filtered_rooms', available_rooms)
                filtered_hotels.append(hotel)

        hotels = filtered_hotels
    else:
        # If no filters applied, set filtered_rooms to all rooms
        for hotel in hotels:
            setattr(hotel, 'filtered_rooms', hotel.rooms)

    # Get current month to determine if it's peak season
    current_month = datetime.now().month
    is_peak_season = current_month in [4, 5, 6, 7, 8, 11, 12]

    # Get cities from database instead of CITY_DATA
    cities = City.query.all()
    cities_data = [{
        'name': city.name,
        'capacity': city.capacity,
        'peak_rate': city.peak_rate,
        'off_peak_rate': city.off_peak_rate
    } for city in cities]

    # Get selected currency
    currency_code = request.args.get('currency', 'GBP')
    currency = Currency.query.filter_by(code=currency_code, is_active=True).first() or \
              Currency.query.filter_by(code='GBP').first()

    # Add currency to template context
    return render_template('index.html',
                         cities=cities_data,
                         is_peak_season=is_peak_season,
                         hotels=hotels,
                         CITY_DATA=CITY_DATA,
                         currency=currency,
                         currencies=Currency.query.filter_by(is_active=True).all())

@app.route('/hotel/<int:hotel_id>')
def hotel_details(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    current_month = datetime.now().month
    is_peak_season = current_month in [4, 5, 6, 7, 8, 11, 12]
    return render_template('hotel_details.html',
                         hotel=hotel,
                         is_peak_season=is_peak_season,
                         CITY_DATA=CITY_DATA)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()

        flash('Registration successful')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))

        flash('Invalid email or password')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    # Add current datetime for comparing with booking dates
    return render_template('profile.html',
                         now=datetime.utcnow())

@app.route('/booking/<int:hotel_id>', methods=['GET', 'POST'])
@login_required
def booking(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    # Get selected currency
    currency_code = request.args.get('currency', 'GBP')
    currency = Currency.query.filter_by(code=currency_code, is_active=True).first() or \
              Currency.query.filter_by(code='GBP').first()

    # Get current month to determine if it's peak season
    current_month = datetime.now().month
    is_peak_season = current_month in [4, 5, 6, 7, 8, 11, 12]

    # Get base rate from CITY_DATA
    base_rate = CITY_DATA[hotel.city]['peak_rate'] if is_peak_season else CITY_DATA[hotel.city]['off_peak_rate']

    if request.method == 'POST':
        try:
            # Get form data
            check_in = datetime.strptime(request.form.get('check_in'), '%Y-%m-%d')
            check_out = datetime.strptime(request.form.get('check_out'), '%Y-%m-%d')
            guests = int(request.form.get('guests'))
            room_id = int(request.form.get('room_id'))

            # Get room details
            room = Room.query.get_or_404(room_id)

            # Calculate room price based on type
            if 'Standard' in room.type or 'Classic' in room.type or 'Business' in room.type:
                room_price = base_rate
            elif 'Double' in room.type or 'Deluxe' in room.type or 'View' in room.type:
                room_price = base_rate * 1.2
            elif 'Suite' in room.type or 'Premium' in room.type or 'Royal' in room.type or 'Executive' in room.type or 'Presidential' in room.type:
                room_price = base_rate * 1.5
            else:
                room_price = base_rate

            # Calculate total price
            days = (check_out - check_in).days
            total_price = (room_price * days) / currency.rate_to_gbp

            # Create booking
            booking = Booking(
                user_id=current_user.id,
                hotel_id=hotel_id,
                room_id=room_id,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                total_price=total_price,
                status='confirmed'
            )

            # Update room availability
            room.available = False

            db.session.add(booking)
            db.session.commit()

            flash('Booking confirmed successfully!')
            return redirect(url_for('booking_confirmation', booking_id=booking.id))

        except Exception as e:
            db.session.rollback()
            flash('Error processing booking. Please try again.')
            return redirect(url_for('booking', hotel_id=hotel_id))

    # For GET request, show the booking form
    room_id = request.args.get('room_id')
    selected_room = None
    if room_id:
        selected_room = Room.query.get(room_id)

    return render_template('booking.html',
                         hotel=hotel,
                         selected_room=selected_room,
                         check_in=request.args.get('check_in'),
                         check_out=request.args.get('check_out'),
                         guests=request.args.get('guests'),
                         currency=currency,
                         currencies=Currency.query.filter_by(is_active=True).all(),
                         CITY_DATA=CITY_DATA,
                         is_peak_season=is_peak_season)

@app.route('/booking/confirmation/<int:booking_id>')
@login_required
def booking_confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return render_template('booking_confirmation.html', booking=booking)

@app.route('/booking/cancel/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def cancellation_page(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Unauthorized')
        return redirect(url_for('profile'))

    if request.method == 'POST':
        # Handle cancellation
        booking.status = 'cancelled'
        booking.room.available = True
        booking.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Booking cancelled successfully')
        return redirect(url_for('profile'))

    return render_template('cancellation.html',
                         booking=booking,
                         now=datetime.utcnow())

@app.route('/search')
def search():
    # Get search parameters
    city = request.args.get('city')
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    room_types = request.args.getlist('room_types[]')
    amenities = request.args.getlist('amenities[]')
    sort = request.args.get('sort', 'price_asc')

    # Build query
    query = Hotel.query

    if city:
        query = query.filter(Hotel.city.ilike(f'%{city}%'))

    if room_types:
        query = query.join(Room).filter(Room.type.in_(room_types))

    if min_price is not None:
        query = query.join(Room).filter(Room.price >= min_price)

    if max_price is not None:
        query = query.join(Room).filter(Room.price <= max_price)

    # Apply sorting
    if sort == 'price_asc':
        query = query.join(Room).order_by(Room.price.asc())
    elif sort == 'price_desc':
        query = query.join(Room).order_by(Room.price.desc())
    elif sort == 'rating_desc':
        query = query.order_by(Hotel.rating.desc())

    hotels = query.all()

    # Get all available room types and amenities for filters
    room_types = db.session.query(Room.type).distinct().all()
    room_types = [r[0] for r in room_types]

    # Pass search parameters back to template
    search = {
        'city': city,
        'check_in': check_in,
        'check_out': check_out,
        'min_price': min_price,
        'max_price': max_price,
        'room_types': room_types,
        'amenities': amenities,
        'sort': sort
    }

    return render_template('search_results.html',
                         hotels=hotels,
                         search=search,
                         room_types=room_types,
                         amenities=['WiFi', 'Pool', 'Gym', 'Restaurant', 'Parking'])

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password) and user.is_admin:
            login_user(user)
            return redirect(url_for('admin_dashboard'))

        flash('Invalid credentials or insufficient permissions')
        return redirect(url_for('admin_login'))

    return render_template('admin/login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    # Get statistics for dashboard
    total_bookings = Booking.query.count()
    total_users = User.query.count()
    total_hotels = Hotel.query.count()
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                         total_bookings=total_bookings,
                         total_users=total_users,
                         total_hotels=total_hotels,
                         recent_bookings=recent_bookings)

@app.route('/admin/hotels')
@login_required
def admin_hotels():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    hotels = Hotel.query.all()
    return render_template('admin/hotels.html', hotels=hotels)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/hotels/add', methods=['GET', 'POST'])
@login_required
def admin_add_hotel():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            hotel = Hotel(
                name=request.form.get('name'),
                city=request.form.get('city'),
                address=request.form.get('address'),
                description=request.form.get('description'),
                image_url=request.form.get('image_url')
            )
            db.session.add(hotel)
            db.session.commit()

            # Add rooms
            room_types = request.form.getlist('room_type[]')
            room_prices = request.form.getlist('room_price[]')
            room_capacities = request.form.getlist('room_capacity[]')

            for i in range(len(room_types)):
                if room_types[i].strip():  # Only add if room type is not empty
                    room = Room(
                        hotel_id=hotel.id,
                        type=room_types[i],
                        price=float(room_prices[i]),
                        capacity=int(room_capacities[i]),
                        available=True
                    )
                    db.session.add(room)

            db.session.commit()
            flash('Hotel added successfully')
            return redirect(url_for('admin_hotels'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding hotel: {str(e)}')
            return redirect(url_for('admin_add_hotel'))

    return render_template('admin/add_hotel.html')

@app.route('/admin/hotels/edit/<int:hotel_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_hotel(hotel_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    hotel = Hotel.query.get_or_404(hotel_id)

    if request.method == 'POST':
        hotel.name = request.form.get('name')
        hotel.city = request.form.get('city')
        hotel.address = request.form.get('address')
        hotel.description = request.form.get('description')
        hotel.image_url = request.form.get('image_url')

        # Update existing rooms
        room_ids = request.form.getlist('room_id[]')
        room_types = request.form.getlist('room_type[]')
        room_prices = request.form.getlist('room_price[]')
        room_capacities = request.form.getlist('room_capacity[]')

        # Get base rate for the city
        base_rate = CITY_DATA[hotel.city]['peak_rate']

        for i in range(len(room_ids)):
            room = Room.query.get(int(room_ids[i]))
            if room:
                room.type = room_types[i]
                # Calculate price based on room type
                if 'Standard' in room_types[i] or 'Classic' in room_types[i] or 'Business' in room_types[i]:
                    room.price = base_rate
                elif 'Double' in room_types[i] or 'Deluxe' in room_types[i] or 'View' in room_types[i]:
                    room.price = base_rate * 1.2
                elif 'Suite' in room_types[i] or 'Premium' in room_types[i] or 'Royal' in room_types[i] or 'Executive' in room_types[i] or 'Presidential' in room_types[i]:
                    room.price = base_rate * 1.5
                else:
                    room.price = base_rate
                room.capacity = int(room_capacities[i])

        db.session.commit()
        flash('Hotel updated successfully')
        return redirect(url_for('admin_hotels'))

    return render_template('admin/edit_hotel.html', hotel=hotel, CITY_DATA=CITY_DATA)

@app.route('/admin/users/<int:user_id>')
@login_required
def admin_user_details(user_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)
    return render_template('admin/user_details.html', user=user)

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')

        # Only update password if provided
        new_password = request.form.get('password')
        if new_password:
            user.password_hash = generate_password_hash(new_password)

        # Only admin can change admin status, and can't remove their own admin status
        if current_user.id != user.id:  # Can't change own admin status
            user.is_admin = 'is_admin' in request.form

        db.session.commit()
        flash('User updated successfully')
        return redirect(url_for('admin_user_details', user_id=user.id))

    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>/toggle-role', methods=['POST'])
@login_required
def admin_toggle_user_role(user_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)

    # Prevent admin from removing their own admin status
    if current_user.id == user.id:
        flash('You cannot change your own admin status')
        return redirect(url_for('admin_users'))

    user.is_admin = not user.is_admin
    db.session.commit()

    flash(f'User role updated successfully. {user.username} is now {"an admin" if user.is_admin else "a regular user"}.')
    return redirect(url_for('admin_users'))

@app.route('/admin/currencies')
@login_required
def admin_currencies():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    currencies = Currency.query.all()
    return render_template('admin/currencies.html', currencies=currencies)

@app.route('/admin/currencies/edit/<int:currency_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_currency(currency_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    currency = Currency.query.get_or_404(currency_id)

    if request.method == 'POST':
        currency.symbol = request.form.get('symbol')
        currency.rate_to_gbp = float(request.form.get('rate_to_gbp'))
        currency.is_active = 'is_active' in request.form

        db.session.commit()
        flash('Currency updated successfully')
        return redirect(url_for('admin_currencies'))

    return render_template('admin/edit_currency.html', currency=currency)

@app.route('/admin/cities')
@login_required
def admin_cities():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    cities = City.query.all()
    return render_template('admin/cities.html', cities=cities)

@app.route('/admin/cities/add', methods=['GET', 'POST'])
@login_required
def admin_add_city():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    if request.method == 'POST':
        city = City(
            name=request.form.get('name'),
            capacity=int(request.form.get('capacity')),
            peak_rate=float(request.form.get('peak_rate')),
            off_peak_rate=float(request.form.get('off_peak_rate'))
        )
        db.session.add(city)
        db.session.commit()
        flash('City added successfully')
        return redirect(url_for('admin_cities'))

    return render_template('admin/edit_city.html', city=None, CITY_DATA=CITY_DATA)

@app.route('/admin/cities/edit/<int:city_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_city(city_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    city = City.query.get_or_404(city_id)

    if request.method == 'POST':
        city.name = request.form.get('name')
        city.capacity = int(request.form.get('capacity'))
        city.peak_rate = float(request.form.get('peak_rate'))
        city.off_peak_rate = float(request.form.get('off_peak_rate'))

        db.session.commit()
        flash('City updated successfully')
        return redirect(url_for('admin_cities'))

    return render_template('admin/edit_city.html', city=city, CITY_DATA=CITY_DATA)

@app.route('/admin/cities/delete/<int:city_id>', methods=['POST'])
@login_required
def admin_delete_city(city_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))

    city = City.query.get_or_404(city_id)
    db.session.delete(city)
    db.session.commit()
    flash('City deleted successfully')
    return redirect(url_for('admin_cities'))

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

def init_example_data():
    # Initialize cities from CITY_DATA
    for city_name, data in CITY_DATA.items():
        if not City.query.filter_by(name=city_name).first():
            city = City(
                name=city_name,
                capacity=data['capacity'],
                peak_rate=data['peak_rate'],
                off_peak_rate=data['off_peak_rate']
            )
            db.session.add(city)

    db.session.commit()

    # Create admin user
    admin = User.query.filter_by(email='admin@wh.com.uk').first()
    if not admin:
        admin = User(
            username='Admin',
            email='admin@wh.com.uk',
            password_hash=generate_password_hash('admin@123!'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

    # Example Hotels with their details
    hotels_data = [
        {
            'name': 'The Grand London Hotel',
            'city': 'London',
            'address': '123 Oxford Street, London, UK',
            'description': 'A luxurious 5-star hotel in the heart of London, offering stunning views of the city skyline. Features include a rooftop restaurant, spa, and premium amenities.',
            'image_url': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 200, 'capacity': 2},
                {'type': 'Deluxe Room', 'price': 300, 'capacity': 2},
                {'type': 'Executive Suite', 'price': 500, 'capacity': 4},
            ]
        },
        {
            'name': 'Edinburgh Castle Hotel',
            'city': 'Edinburgh',
            'address': '45 Royal Mile, Edinburgh, UK',
            'description': 'Historic hotel with stunning views of Edinburgh Castle. Combines traditional Scottish hospitality with modern luxury.',
            'image_url': 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Classic Room', 'price': 160, 'capacity': 2},
                {'type': 'Castle View Room', 'price': 250, 'capacity': 2},
                {'type': 'Royal Suite', 'price': 400, 'capacity': 3},
            ]
        },
        {
            'name': 'Manchester City Center Hotel',
            'city': 'Manchester',
            'address': '78 Deansgate, Manchester, UK',
            'description': "Modern hotel in Manchester's vibrant city center. Perfect for both business and leisure travelers.",
            'image_url': 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Business Room', 'price': 180, 'capacity': 2},
                {'type': 'Premium Room', 'price': 250, 'capacity': 2},
                {'type': 'Family Suite', 'price': 350, 'capacity': 4},
            ]
        },
        {
            'name': 'Glasgow Riverside Hotel',
            'city': 'Glasgow',
            'address': '234 Clyde Street, Glasgow, UK',
            'description': 'Riverside hotel offering panoramic views of the River Clyde. Features a wellness center and gourmet dining.',
            'image_url': 'https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'River View Room', 'price': 150, 'capacity': 2},
                {'type': 'Deluxe Suite', 'price': 280, 'capacity': 3},
                {'type': 'Presidential Suite', 'price': 450, 'capacity': 4},
            ]
        },
        {
            'name': 'Birmingham Business Hotel',
            'city': 'Birmingham',
            'address': '56 Broad Street, Birmingham, UK',
            'description': "Contemporary hotel in Birmingham's business district. Features modern conference facilities and upscale dining.",
            'image_url': 'https://images.unsplash.com/photo-1564501049412-61c2a3083791?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Business Room', 'price': 150, 'capacity': 1},
                {'type': 'Executive Room', 'price': 220, 'capacity': 2},
                {'type': 'Business Suite', 'price': 320, 'capacity': 2},
            ]
        },
        {
            'name': 'Aberdeen Harbour Hotel',
            'city': 'Aberdeen',
            'address': '123 Union Street, Aberdeen, UK',
            'description': 'Modern hotel overlooking Aberdeen harbour with stunning sea views. Features a seafood restaurant and maritime-themed decor.',
            'image_url': 'https://images.unsplash.com/photo-1582719508461-905c673771fd?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 140, 'capacity': 2},
                {'type': 'Deluxe Room', 'price': 182, 'capacity': 2},
                {'type': 'Sea View Suite', 'price': 210, 'capacity': 3},
            ]
        },
        {
            'name': 'Belfast City Hotel',
            'city': 'Belfast',
            'address': '45 Victoria Street, Belfast, UK',
            'description': 'Contemporary hotel in the heart of Belfast, close to major attractions and shopping districts.',
            'image_url': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 130, 'capacity': 2},
                {'type': 'Deluxe Double', 'price': 169, 'capacity': 2},
                {'type': 'Family Suite', 'price': 195, 'capacity': 4},
            ]
        },
        {
            'name': 'Bristol Harbourside Hotel',
            'city': 'Bristol',
            'address': '78 Welsh Back, Bristol, UK',
            'description': 'Waterfront hotel with views of Bristol Harbour. Contemporary design with a focus on sustainability.',
            'image_url': 'https://images.unsplash.com/photo-1582719508461-905c673771fd?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 140, 'capacity': 2},
                {'type': 'Harbour View Room', 'price': 182, 'capacity': 2},
                {'type': 'Executive Suite', 'price': 210, 'capacity': 3},
            ]
        },
        {
            'name': 'Cardiff Bay Hotel',
            'city': 'Cardiff',
            'address': '234 Cardiff Bay, Cardiff, UK',
            'description': 'Modern hotel in Cardiff Bay with views of the waterfront and easy access to the Wales Millennium Centre.',
            'image_url': 'https://images.unsplash.com/photo-1564501049412-61c2a3083791?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 130, 'capacity': 2},
                {'type': 'Bay View Room', 'price': 169, 'capacity': 2},
                {'type': 'Premium Suite', 'price': 195, 'capacity': 3},
            ]
        },
        {
            'name': 'Newcastle Central Hotel',
            'city': 'New Castle',
            'address': '56 Grey Street, Newcastle, UK',
            'description': 'Historic hotel in a Georgian building, located in the heart of Newcastle\'s cultural quarter.',
            'image_url': 'https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 120, 'capacity': 2},
                {'type': 'Deluxe Room', 'price': 156, 'capacity': 2},
                {'type': 'Georgian Suite', 'price': 180, 'capacity': 4},
            ]
        },
        {
            'name': 'Norwich Cathedral Hotel',
            'city': 'Norwich',
            'address': '89 Cathedral Close, Norwich, UK',
            'description': 'Boutique hotel with views of Norwich Cathedral, combining medieval charm with modern comfort.',
            'image_url': 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 130, 'capacity': 2},
                {'type': 'Cathedral View Room', 'price': 169, 'capacity': 2},
                {'type': 'Heritage Suite', 'price': 195, 'capacity': 3},
            ]
        },
        {
            'name': 'Nottingham Castle Hotel',
            'city': 'Nottingham',
            'address': '12 Castle Road, Nottingham, UK',
            'description': 'Elegant hotel near Nottingham Castle, featuring a rooftop restaurant with panoramic city views.',
            'image_url': 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 130, 'capacity': 2},
                {'type': 'Castle View Room', 'price': 169, 'capacity': 2},
                {'type': 'Royal Suite', 'price': 195, 'capacity': 4},
            ]
        },
        {
            'name': 'Oxford Spires Hotel',
            'city': 'Oxford',
            'address': '45 High Street, Oxford, UK',
            'description': 'Classic hotel in the heart of Oxford, surrounded by historic colleges and architectural beauty.',
            'image_url': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 180, 'capacity': 2},
                {'type': 'College View Room', 'price': 234, 'capacity': 2},
                {'type': 'Presidential Suite', 'price': 270, 'capacity': 3},
            ]
        },
        {
            'name': 'Plymouth Hoe Hotel',
            'city': 'Plymouth',
            'address': '78 Hoe Road, Plymouth, UK',
            'description': 'Seafront hotel with spectacular views of Plymouth Sound and the famous Hoe promenade.',
            'image_url': 'https://images.unsplash.com/photo-1582719508461-905c673771fd?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 180, 'capacity': 2},
                {'type': 'Sea View Room', 'price': 234, 'capacity': 2},
                {'type': 'Lighthouse Suite', 'price': 270, 'capacity': 4},
            ]
        },
        {
            'name': 'Swansea Marina Hotel',
            'city': 'Swansea',
            'address': '234 Marina, Swansea, UK',
            'description': 'Modern hotel overlooking Swansea Marina, perfect for both business and leisure travelers.',
            'image_url': 'https://images.unsplash.com/photo-1564501049412-61c2a3083791?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 130, 'capacity': 2},
                {'type': 'Marina View Room', 'price': 169, 'capacity': 2},
                {'type': 'Executive Suite', 'price': 195, 'capacity': 3},
            ]
        },
        {
            'name': 'Bournemouth Beach Hotel',
            'city': 'Bournemouth',
            'address': '56 West Cliff, Bournemouth, UK',
            'description': 'Beachfront hotel with direct access to Bournemouth\'s golden sandy beach and historic pier.',
            'image_url': 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 130, 'capacity': 2},
                {'type': 'Sea View Room', 'price': 169, 'capacity': 2},
                {'type': 'Beach Suite', 'price': 195, 'capacity': 4},
            ]
        },
        {
            'name': 'Kent Country House Hotel',
            'city': 'Kent',
            'address': '123 Garden Way, Canterbury, Kent, UK',
            'description': 'Historic country house hotel set in beautiful Kent countryside with extensive gardens and spa facilities.',
            'image_url': 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80',
            'rooms': [
                {'type': 'Standard Room', 'price': 140, 'capacity': 2},
                {'type': 'Garden View Room', 'price': 182, 'capacity': 2},
                {'type': 'Country Suite', 'price': 210, 'capacity': 3},
            ]
        }
    ]

    # Add hotels and their rooms to the database
    for hotel_data in hotels_data:
        # Check if hotel already exists
        existing_hotel = Hotel.query.filter_by(name=hotel_data['name']).first()
        if not existing_hotel:
            hotel = Hotel(
                name=hotel_data['name'],
                city=hotel_data['city'],
                address=hotel_data['address'],
                description=hotel_data['description'],
                image_url=hotel_data['image_url']
            )
            db.session.add(hotel)
            db.session.flush()  # To get the hotel ID

            # Add rooms for this hotel
            for room_data in hotel_data['rooms']:
                room = Room(
                    hotel_id=hotel.id,
                    type=room_data['type'],
                    price=room_data['price'],
                    capacity=room_data['capacity'],
                    available=True
                )
                db.session.add(room)

    db.session.commit()

    # Initialize default currencies
    currencies_data = [
        {'code': 'GBP', 'symbol': '£', 'rate_to_gbp': 1.0},
        {'code': 'EUR', 'symbol': '€', 'rate_to_gbp': 1.17},
        {'code': 'USD', 'symbol': '$', 'rate_to_gbp': 1.27}
    ]

    for currency_data in currencies_data:
        if not Currency.query.filter_by(code=currency_data['code']).first():
            currency = Currency(**currency_data)
            db.session.add(currency)

    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        # Drop all tables and recreate them
        db.drop_all()
        db.create_all()
        init_example_data()
    app.run(debug=True)
