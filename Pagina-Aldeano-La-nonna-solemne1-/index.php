<html>
    <head>
        <title>Pagina Principal</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>        
    </head>
        <title>Restaurante "La nonna"</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
    
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
        <!--Navbar -->
        <nav class="navbar navbar-expand-sm bg-dark navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="index.php">Logo</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                    <span class="navbar-toggler-icon"></span>
                </button> 
                <div class="collapse navbar-collapse" id="collapsibleNavbar">
                    <ul class="navbar-nav">            
                        <li class="nav-item">
                            <a class="nav-link" href="carta.php">Carta</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="historial.php">Historial</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="carrito.php">Carrito</a>
                        </li>                           
                    </ul>
                </div>  
                <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#myModal">Acceder</button>                             
            </div>
        </nav>
    <!-- Contenedor principal centrado -->
    <div class="container my-auto py-4">
        
        <!-- Recuadro contenedor con tono oscuro translúcido -->
        <div class="p-4 rounded-4 shadow-lg mx-auto" 
            style="max-width: 900px; background-color: rgba(20, 5, 10, 0.75); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.15);">
            
            <h3 class="text-center text-white mb-4 fw-bold" style="letter-spacing: 1px;">Platos Mas Pedidos</h3>

            <div class="row g-4 justify-content-center text-center">
                
                <!-- Plato 1 -->
                <div class="col-12 col-md-4">
                    <div class="card h-100 bg-dark text-white border-secondary shadow-sm">
                        <!-- Ajusta la ruta a tu archivo real -->
                        <img src="imagenes/fideos con salsa.jpg" class="card-img-top" alt="Spaghetti Bolognesa" style="height: 160px; object-fit: cover;">
                        <div class="card-body py-2">
                            <a href="carta.php" class="text-decoration-none text-warning fw-bold stretched-link">Spaghetti Bolognesa</a>
                        </div>
                    </div>
                </div>

                <!-- Plato 2 -->
                <div class="col-12 col-md-4">
                    <div class="card h-100 bg-dark text-white border-secondary shadow-sm">
                        <!-- Ajusta la ruta a tu archivo real -->
                        <img src="imagenes/albondigas.jpg" class="card-img-top" alt="Fideos con albóndigas" style="height: 160px; object-fit: cover;">
                        <div class="card-body py-2">
                            <a href="carta.php" class="text-decoration-none text-warning fw-bold stretched-link">Fideos con albóndigas</a>
                        </div>
                    </div>
                </div>

                <!-- Plato 3 -->
                <div class="col-12 col-md-4">
                    <div class="card h-100 bg-dark text-white border-secondary shadow-sm">
                        <!-- Ajusta la ruta a tu archivo real -->
                        <img src="imagenes/lasana.jpg" class="card-img-top" alt="Lasaña" style="height: 160px; object-fit: cover;">
                        <div class="card-body py-2">
                            <a href="carta.php" class="text-decoration-none text-warning fw-bold stretched-link">Lasaña de carne</a>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>
        <!--Footer-->
    <body>
        <!--Modal Principal-->
        <div class="modal fade" id="myModal">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <!-- Modal Header -->
                    <div class="modal-header">
                        <h4 class="modal-title">Autenticacion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <!-- Modal body -->
                    <div class="modal-body">
                        <div class="row">
                            <!-- Izquierda: Usuario / Crear cuenta -->
                            <div class="col-sm-6 border-end">
                                <h5>Usuario</h5>
                                <form action="registro.php">
                                    <div class="mb-3 mt-3">
                                        <label for="emailUser" class="form-label">Email:</label>
                                        <input type="email" class="form-control" id="emailUser" placeholder="Enter email" name="email">
                                    </div>
                                    <button type="submit" class="btn btn-primary mb-3">Crear cuenta</button>
                                </form>
                                <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#loginModal">Iniciar sesion</button>
                            </div>

                            <!-- Derecha: Trabajadores -->
                            <div class="col-sm-6">
                                <h5>Trabajadores</h5>
                                <form action="trabajador.php">
                                    <div class="mb-3 mt-3">
                                        <label for="emailTrab" class="form-label">Email:</label>
                                        <input type="email" class="form-control" id="emailTrab" placeholder="Enter email" name="email">
                                    </div>
                                    <div class="mb-3">
                                        <label for="pwdTrab" class="form-label">Password:</label>
                                        <input type="password" class="form-control" id="pwdTrab" placeholder="Enter password" name="pswd">
                                    </div>
                                    <button type="submit" class="btn btn-primary">Login</button>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
    <!-- Contenedor de Reseñas de Clientes -->
    <div class="container my-4">
        <div class="p-4 rounded-4 shadow-lg mx-auto" 
             style="max-width: 900px; background-color: rgba(20, 5, 10, 0.75); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.15);">
            
            <h4 class="text-center text-warning mb-4 fw-bold" style="letter-spacing: 1px;">Opiniones de Nuestros Clientes</h4>

            <div class="row g-4 justify-content-center">
                
                <!-- Reseña 1: 5/5 -->
                <div class="col-12 col-md-6">
                    <div class="p-3 rounded-3 h-100 border border-secondary border-opacity-25" style="background-color: rgba(255, 255, 255, 0.05);">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="text-white fw-bold">Camila Rojas</span>
                            <div class="text-warning small">
                                <i class="bi bi-star-fill"></i>
                                <i class="bi bi-star-fill"></i>
                                <i class="bi bi-star-fill"></i>
                                <i class="bi bi-star-fill"></i>
                                <i class="bi bi-star-fill"></i>
                                <span class="text-white ms-1 fw-bold">5/5</span>
                            </div>
                        </div>
                        <p class="text-white-50 small mb-0">
                            "La pasta fresca casera es simplemente de otro nivel. El sabor de la salsa y el ambiente te transportan directo a Italia. ¡Totalmente recomendado!"
                        </p>
                    </div>
                </div>

                <!-- Reseña 2: 4.5/5 -->
                <div class="col-12 col-md-6">
                    <div class="p-3 rounded-3 h-100 border border-secondary border-opacity-25" style="background-color: rgba(255, 255, 255, 0.05);">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="text-white fw-bold">Ignacio Silva</span>
                            <div class="text-warning small">
                                <i class="bi bi-star-fill"></i>
                                <i class="bi bi-star-fill"></i>
                                <i class="bi bi-star-fill"></i>
                                <i class="bi bi-star-fill"></i>
                                <i class="bi bi-star-half"></i>
                                <span class="text-white ms-1 fw-bold">4.5/5</span>
                            </div>
                        </div>
                        <p class="text-white-50 small mb-0">
                            "Excelente relación precio-calidad. La lasaña llega bien caliente y con abundante queso fundido. Muy rápida atención."
                        </p>
                    </div>
                </div>

            </div>
        </div>
    </div>
        <!--Modal Inicio Sesion Usuario-->
        <div class="modal fade" id="loginModal">
            <div class="modal-dialog">
                <div class="modal-content">
                    <!-- Modal Header -->
                    <div class="modal-header">
                        <h4 class="modal-title">Inicio de sesion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <!-- Modal body -->
                    <div class="modal-body">
                        <form action="empresa.php">
                            <div class="mb-3 mt-3">
                                <label for="email" class="form-label">Email:</label>
                                <input type="email" class="form-control" id="email" placeholder="Enter email" name="email">
                            </div>
                            <div class="mb-3">
                                <label for="pwd" class="form-label">Password:</label>
                                <input type="password" class="form-control" id="pwd" placeholder="Enter password" name="pswd">
                            </div>
                            <div class="form-check mb-3">
                                <label class="form-check-label">
                                    <input class="form-check-input" type="checkbox" name="remember"> Remember me
                                </label>
                            </div>
                            <button type="submit" class="btn btn-primary">Login</button>
                        </form>
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-toggle="modal" data-bs-target="#myModal">Volver</button>
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
        <!-- Footer -->
    <div class="container-fluid bg-dark mt-auto py-3 text-white text-center">
        <div class="row">
            <div class="col-4 text-start ps-4">
                <a href="quienes_somos.php" style="color:gray; text-decoration: none;"><strong>Quienes somos</strong>
                </a>
            </div>
            <div 
                class="col-4" style="color:gray"><strong>LocalLaNonna@gmail.com</strong>
            </div>
            <div class="col-4"></div>
        </div>
    </div>
</html>