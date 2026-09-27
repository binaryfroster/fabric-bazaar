"""Authentication forms — Register (Customer or Company) & Login."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models.user import User


class RegistrationForm(FlaskForm):
    role       = SelectField('I am registering as',
                             choices=[('customer', '🛍️  Customer — I want to buy products'),
                                      ('company', '🏭  Company / Seller — I want to sell products'),
                                      ('delivery', '🏍️  Delivery Partner — I deliver orders')],
                             default='customer')
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=64)])
    last_name  = StringField('Last Name',  validators=[DataRequired(), Length(min=2, max=64)])
    email      = StringField('Email Address', validators=[DataRequired(), Email()])
    password   = PasswordField('Password',
                               validators=[DataRequired(),
                               Length(min=8, message='Password must be at least 8 characters.')])
    confirm    = PasswordField('Confirm Password',
                               validators=[DataRequired(),
                               EqualTo('password', message='Passwords must match.')])
    submit     = SubmitField('Create Account')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('An account with this email already exists.')


class LoginForm(FlaskForm):
    email    = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Keep me signed in')
    submit   = SubmitField('Sign In')
