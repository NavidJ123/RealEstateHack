create table if not exists properties (
  id text primary key,
  address text not null,
  zipcode text not null,
  sqft int,
  type text,
  last_sale_price numeric,
  last_sale_date date,
  current_est_value numeric,
  est_monthly_rent numeric,
  image_url text
);

create table if not exists market_stats (
  zipcode text,
  date date,
  median_price numeric,
  median_rent numeric,
  inventory int,
  dom int,
  income numeric,
  vacancy_rate numeric,
  primary key(zipcode, date)
);

create table if not exists comps (
  comp_id text primary key,
  property_id text references properties(id),
  address text,
  sale_price numeric,
  sale_date date,
  sqft int,
  distance_mi numeric
);
