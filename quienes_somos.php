<html>
    <head>
        <title>Quienes Somos - Restaurante "La Nonna"</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
        <link rel="stylesheet" href="style.css">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>        
    </head>
    <body class="d-flex flex-column min-vh-100">
        <!-- Navbar -->
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
                    </ul>
                </div>  
                <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#myModal">Acceder</button>                             
            </div>
        </nav>

        <!-- Contenedor Principal (Wireframe: Quienes Somos) -->
        <div class="container my-auto py-4" style="max-width: 900px;">
            
            <!-- Bloque Superior: Texto descriptivo -->
            <div class="p-4 rounded-4 shadow-lg mb-4 text-center text-white" 
                style="background-color: rgba(20, 5, 10, 0.75); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.15);">
                <h3 class="text-warning fw-bold mb-3" style="letter-spacing: 1px;">Quienes somos</h3>
                <p class="mb-0 text-light" style="line-height: 1.6;">
                    En Pastas Frescas "La Nonna" llevamos la verdadera tradición de la cocina italiana directo a tu mesa en Maipú. 
                    Elaboramos artesanalmente cada porción de ravioles, lasañas y tallarines frescos con recetas tradicionales de familia, 
                    seleccionando siempre ingredientes de la más alta calidad para ofrecerte un sabor único e inconfundible.
                </p>
            </div>

            <!-- Bloque Inferior: Fotos del local o platos más pedidos -->
            <div class="p-4 rounded-4 shadow-lg text-center text-white" 
                style="background-color: rgba(20, 5, 10, 0.75); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.15);">
                <h5 class="text-warning fw-bold mb-3">Nuestro Local y Especialidades</h5>
                
                <div class="row g-3 justify-content-center">
                    <div class="col-12 col-md-6">
                        <div class="card bg-dark text-white border-secondary">
                            <img src="imagenes/lasana.jpg" class="card-img-top" alt="Nuestra Cocina" style="height: 180px; object-fit: cover;">
                            <div class="card-body py-2">
                                <p class="card-text small text-white-50 mb-0">Preparación artesanal diaria</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-12 col-md-6">
                        <div class="card bg-dark text-white border-secondary">
                            <img src="imagenes/ravioles.jpg" class="card-img-top" alt="Platos Destacados" style="height: 180px; object-fit: cover;">
                            <div class="card-body py-2">
                                <p class="card-text small text-white-50 mb-0">Ravioles frescos hechos a mano</p>
                            </div>
                        </div>
                    </div>
                </div>

            </div>
        </div>

        <!-- Modal Principal de Autenticación -->
        <div class="modal fade" id="myModal">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h4 class="modal-title">Autenticacion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
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
                    <div class="modal-footer">
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal Inicio Sesion Usuario -->
        <div class="modal fade" id="loginModal">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h4 class="modal-title">Inicio de sesion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
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
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-toggle="modal" data-bs-target="#myModal">Volver</button>
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>


        <script src="js/app.js"></script>
    </body>
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
